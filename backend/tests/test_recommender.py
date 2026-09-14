"""
Unit and Integration Test Suite for the Music Recommender System.
Tests:
- Audio feature extraction & normalization
- Qdrant Vector Store indexing and search
- Zero-replay session cooldown enforcement
- Obscurity formula behavior (underground vs mainstream)
- FastAPI API endpoints
"""
import pytest
import numpy as np
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.audio_extractor import AudioFeatureExtractor
from backend.app.services.vector_store import VectorStore
from backend.app.services.recommender import RecommenderEngine
from backend.app.services.session_manager import SessionManager
from backend.app.models.schemas import (
    Track,
    AcousticFeatures,
    RecommendationRequest,
    SessionFeedbackRequest
)

client = TestClient(app)

def test_audio_feature_extractor_synthetic():
    extractor = AudioFeatureExtractor()
    sr = 16000
    duration = 5.0  # 5 seconds
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    
    # 440 Hz (A4) Sine wave with 120 BPM amplitude pulse
    sine = np.sin(2 * np.pi * 440.0 * t)
    pulse = (np.sin(2 * np.pi * (120 / 60) * t) ** 2)
    audio = sine * pulse

    features = extractor.extract_features_from_audio(audio, sr=sr)
    
    assert features.bpm > 0
    assert 0.0 <= features.energy <= 1.0
    assert 0.0 <= features.brightness <= 1.0
    assert len(features.embedding) == 64
    # Embedding must be unit normalized
    vec_norm = np.linalg.norm(features.embedding)
    assert abs(vec_norm - 1.0) < 1e-4

def test_vector_store_in_memory():
    store = VectorStore(in_memory=True)
    
    dummy_features = AcousticFeatures(
        bpm=128.0,
        energy=0.8,
        danceability=0.9,
        brightness=0.7,
        tonal_energy=0.6,
        harmonic_key="Am",
        embedding=[0.1] * 64
    )
    # Normalize dummy vector
    norm_vec = (np.array(dummy_features.embedding) / np.linalg.norm(dummy_features.embedding)).tolist()
    dummy_features.embedding = norm_vec

    track = Track(
        track_id="test-track-123",
        youtube_video_id="dQw4w9WgXcQ",
        title="Test Acid Wave",
        channel_name="Acid Vault",
        duration_seconds=300,
        view_count=500,
        genre_tags=["techno"],
        acoustic_features=dummy_features
    )

    store.upsert_track(track)
    retrieved = store.get_track_by_id("test-track-123")
    assert retrieved is not None
    assert retrieved["title"] == "Test Acid Wave"
    assert retrieved["duration_seconds"] == 300

    results = store.search_similar(norm_vec, limit=5)
    assert len(results) >= 1
    assert results[0]["track_id"] == "test-track-123"

def test_zero_replay_session_cooldown():
    session_mgr = SessionManager()
    session = session_mgr.get_or_create_session("test_session_abc")
    
    assert not session.is_in_cooldown("track-1")
    
    # Simulate playing track-1
    session_mgr.record_feedback("test_session_abc", "track-1", "COMPLETED")
    assert session.is_in_cooldown("track-1")
    
    # Simulate skipping track-2
    session_mgr.record_feedback("test_session_abc", "track-2", "SKIPPED")
    assert session.is_in_cooldown("track-2")
    
    cooldowns = session.get_all_cooldown_ids()
    assert "track-1" in cooldowns
    assert "track-2" in cooldowns
    assert "track-3" not in cooldowns

def test_obscurity_scoring_formula():
    engine = RecommenderEngine(max_views_normalizer=50_000_000)
    
    obscure_score = engine.calculate_obscurity_score(view_count=100)
    viral_score = engine.calculate_obscurity_score(view_count=100_000_000)
    
    assert obscure_score > 0.70  # Low views get high obscurity
    assert viral_score == 0.0    # Capped at 0 for ultra viral hits
    assert obscure_score > viral_score

def test_api_health():
    with TestClient(app) as test_client:
        res = test_client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["indexed_tracks"] >= 20

def test_api_recommendation_flow():
    with TestClient(app) as test_client:
        # 1. Request recommendations
        payload = {
            "session_token": "pytest_session_001",
            "obscurity_factor": 0.8,
            "batch_size": 5
        }
        res = test_client.post("/api/v1/recommendations/next", json=payload)
        assert res.status_code == 200
        data = res.json()
        
        items = data["items"]
        assert len(items) > 0
        assert len(items) <= 5
        
        first_track_id = items[0]["track_id"]
        
        # 2. Record feedback that first track was played
        fb_res = test_client.post("/api/v1/sessions/feedback", json={
            "session_token": "pytest_session_001",
            "track_id": first_track_id,
            "event_type": "COMPLETED",
            "listen_duration_seconds": 200
        })
        assert fb_res.status_code == 200
        
        # 3. Request next batch - first_track_id must NEVER be in the new recommendations
        res2 = test_client.post("/api/v1/recommendations/next", json=payload)
        assert res2.status_code == 200
        data2 = res2.json()
        
        rec_ids = [t["track_id"] for t in data2["items"]]
        assert first_track_id not in rec_ids, "Zero-replay violation: previously played track was re-recommended!"

def test_fast_path_check_url():
    with TestClient(app) as test_client:
        # Check known catalog track (seed catalog has "4xDzrJKXOOY" or others)
        catalog_res = test_client.get("/api/v1/catalog/tracks?limit=1")
        assert catalog_res.status_code == 200
        tracks = catalog_res.json()["tracks"]
        assert len(tracks) > 0
        known_track = tracks[0]
        
        # Test fast path hit
        res = test_client.post("/api/v1/catalog/check-url", json={
            "youtube_url": f"https://www.youtube.com/watch?v={known_track['youtube_video_id']}"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["exists"] is True
        assert data["track"]["youtube_video_id"] == known_track["youtube_video_id"]

        # Test fast path miss
        res_miss = test_client.post("/api/v1/catalog/check-url", json={
            "youtube_url": "https://www.youtube.com/watch?v=nonexistent999"
        })
        assert res_miss.status_code == 200
        data_miss = res_miss.json()
        assert data_miss["exists"] is False
