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

def test_soft_fatigue_cooldown():
    import uuid
    token = f"test_session_{uuid.uuid4()}"
    session_mgr = SessionManager()
    session = session_mgr.get_or_create_session(token)
    
    assert not session.is_hard_buffered("track-1")
    assert session.get_fatigue_penalty("track-1") == 0.0
    
    # Simulate playing track-1
    session_mgr.record_feedback(token, "track-1", "COMPLETED")
    assert session.is_hard_buffered("track-1")
    assert session.get_fatigue_penalty("track-1") == 1.0
    
    # Simulate skipping track-2
    session_mgr.record_feedback(token, "track-2", "SKIPPED")
    assert session.is_hard_buffered("track-2")
    
    # Simulate playing 20 other tracks (track-1 with K_COMPLETED=50 and track-2 with K_SKIPPED=30 should still be hard buffered)
    for i in range(20):
        session_mgr.record_feedback(token, f"filler-track-{i}", "COMPLETED")
    
    assert session.is_hard_buffered("track-1")
    assert session.is_hard_buffered("track-2")

    # Simulate playing 35 more tracks (55 total > K_COMPLETED=50)
    for i in range(20, 55):
        session_mgr.record_feedback(token, f"filler-track-{i}", "COMPLETED")
    
    # track-1 should now be out of hard buffer, but have a soft decaying penalty
    assert not session.is_hard_buffered("track-1")
    penalty_1 = session.get_fatigue_penalty("track-1")
    assert 0.0 < penalty_1 < 0.60, f"Expected decayed penalty, got {penalty_1}"


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

def test_qenet_classification():
    extractor = AudioFeatureExtractor()
    
    # Synthetic C-Tizita Major pentatonic chroma [1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0]
    chroma_tizita = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0])
    mode, submode, conf = extractor.classify_qenet_from_chroma(chroma_tizita)
    assert mode == "Tizita"
    assert "Major" in submode
    assert conf > 0.8

    # Synthetic Bati Major pentatonic chroma [1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 0, 1]
    chroma_bati = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0])
    mode, submode, conf = extractor.classify_qenet_from_chroma(chroma_bati)
    assert mode == "Bati"
    assert "Major" in submode
    assert conf > 0.8

def test_galaxy_and_presets_api():
    with TestClient(app) as test_client:
        # 1. Galaxy coordinates endpoint
        res_galaxy = test_client.get("/api/v1/catalog/galaxy")
        assert res_galaxy.status_code == 200
        galaxy_data = res_galaxy.json()
        assert "points" in galaxy_data
        assert len(galaxy_data["points"]) >= 20
        first_pt = galaxy_data["points"][0]
        assert "galaxy_x" in first_pt
        assert "galaxy_y" in first_pt
        assert -1.0 <= first_pt["galaxy_x"] <= 1.0
        assert -1.0 <= first_pt["galaxy_y"] <= 1.0
        assert "qenet_mode" in first_pt

        # 2. Qenet modes catalog endpoint
        res_modes = test_client.get("/api/v1/catalog/qenet-modes")
        assert res_modes.status_code == 200
        modes_data = res_modes.json()["modes"]
        assert len(modes_data) == 4
        mode_names = [m["name_en"] for m in modes_data]
        assert "Tizita" in mode_names
        assert "Bati" in mode_names
        assert "Ambassel" in mode_names
        assert "Anchihoye" in mode_names

        # 3. Vibe presets catalog endpoint
        res_vibes = test_client.get("/api/v1/catalog/vibe-presets")
        assert res_vibes.status_code == 200
        vibes_data = res_vibes.json()["presets"]
        assert len(vibes_data) == 4

        # 4. Recommendation with Qenet filter
        res_qenet_filter = test_client.post("/api/v1/recommendations/next", json={
            "session_token": "pytest_qenet_session",
            "qenet_filter": "Tizita",
            "batch_size": 5
        })
        assert res_qenet_filter.status_code == 200
        qenet_items = res_qenet_filter.json()["items"]
        for item in qenet_items:
            assert item.get("qenet_mode") == "Tizita"

        # 5. Recommendation with Vibe Preset
        res_vibe_filter = test_client.post("/api/v1/recommendations/next", json={
            "session_token": "pytest_vibe_session",
            "vibe_preset": "eskista_beat",
            "batch_size": 5
        })
        assert res_vibe_filter.status_code == 200
        vibe_items = res_vibe_filter.json()["items"]
        assert len(vibe_items) > 0

def test_vault_storage_and_sync():
    with TestClient(app) as test_client:
        sample_starred = [
            {
                "track_id": "test-fav-001",
                "youtube_video_id": "TCpiaKDJX7A",
                "title": "Erè Mèla Mèla",
                "channel_name": "Mahmoud Ahmed",
                "duration_seconds": 275,
                "bpm": 120.0,
                "qenet_mode": "Anchihoye",
                "era": "Golden 70s"
            }
        ]
        # 1. Post to sync vault
        res_sync = test_client.post("/api/v1/vault/starred", json={"starred_tracks": sample_starred})
        assert res_sync.status_code == 200
        sync_data = res_sync.json()
        assert sync_data["status"] == "success"
        assert sync_data["count"] == 1

        # 2. Get from vault endpoint
        res_get = test_client.get("/api/v1/vault/starred")
        assert res_get.status_code == 200
        get_data = res_get.json()
        assert get_data["total_starred"] >= 1
        saved_titles = [t["title"] for t in get_data["starred_tracks"]]
        assert "Erè Mèla Mèla" in saved_titles

        # 3. Test Session Vault Sync with taste centroid
        res_session_sync = test_client.post("/api/v1/sessions/vault/sync", json={
            "session_token": "pytest_taste_session",
            "liked_track_ids": ["test-fav-001"]
        })
        assert res_session_sync.status_code == 200
        assert res_session_sync.json()["status"] == "synced"
        assert res_session_sync.json()["liked_count"] == 1

def test_youtube_url_parsing_robustness():
    """Test extracting YouTube IDs from standard, shorts, music, and timestamped links."""
    from backend.app.services.ingest_service import ingest_service

    test_urls = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?si=abcdef123&t=45", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://music.youtube.com/watch?v=dQw4w9WgXcQ&feature=share", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ?t=10", "dQw4w9WgXcQ"),
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ")
    ]
    for url, expected_id in test_urls:
        assert ingest_service.extract_youtube_id(url) == expected_id, f"Failed on {url}"

def test_unavailable_embed_restriction_handling():
    """Test that UNAVAILABLE events do not apply heavy K=30 skip penalties."""
    import uuid
    token = f"test_unavail_{uuid.uuid4()}"
    mgr = SessionManager()
    session = mgr.get_or_create_session(token)

    # Record UNAVAILABLE error
    mgr.record_feedback(token, "broken-track-001", "UNAVAILABLE")
    
    # Should have a short buffer (<=3), but 0.0 fatigue penalty once past step 3
    assert session.is_hard_buffered("broken-track-001")
    
    # Simulate playing 4 other tracks
    for i in range(4):
        mgr.record_feedback(token, f"filler-{i}", "COMPLETED")
    
    # broken-track-001 should NOT be locked in 30-track skip buffer!
    assert not session.is_hard_buffered("broken-track-001")
    assert session.get_fatigue_penalty("broken-track-001") == 0.0

def test_emergency_stage4_fallback_never_empty():
    """Test that recommendation queue never returns empty even under extreme constraints."""
    with TestClient(app) as test_client:
        # Request batch under an obscure filter and all tracks in local exclusion
        all_tracks_res = test_client.get("/api/v1/catalog/tracks?limit=100")
        all_ids = [t["track_id"] for t in all_tracks_res.json()["tracks"]]

        res = test_client.post("/api/v1/recommendations/next", json={
            "session_token": "pytest_emergency_session",
            "qenet_filter": "Anchihoye",
            "batch_size": 5,
            "excluded_track_ids": all_ids[:20]
        })
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) > 0, "Emergency fallback failed to return items"

def test_discovery_prioritizes_fresh_unplayed_over_liked():
    """Test that the discovery engine prioritizes fresh unplayed songs over already-liked tracks."""
    with TestClient(app) as test_client:
        import uuid
        session_token = f"pytest_fresh_discovery_{uuid.uuid4()}"

        # 1. Fetch tracks and like 3 of them
        all_tracks_res = test_client.get("/api/v1/catalog/tracks?limit=10")
        tracks = all_tracks_res.json()["tracks"]
        liked_ids = [t["track_id"] for t in tracks[:3]]

        # Sync liked tracks to session
        test_client.post("/api/v1/sessions/sync-vault", json={
            "session_token": session_token,
            "liked_track_ids": liked_ids
        })

        # 2. Request recommendations
        rec_res = test_client.post("/api/v1/recommendations/next", json={
            "session_token": session_token,
            "batch_size": 6
        })
        assert rec_res.status_code == 200
        items = rec_res.json()["items"]
        assert len(items) > 0

        # Verify that recommended items prioritize unplayed tracks and do NOT promote the liked tracks to the top
        rec_ids = [t["track_id"] for t in items]
        unplayed_count = sum(1 for tid in rec_ids if tid not in liked_ids)
        
        # High ratio of fresh discoveries
        assert unplayed_count >= len(items) - 1, f"Expected predominantly fresh tracks, got {rec_ids} vs liked {liked_ids}"

def test_dual_key_youtube_id_and_uuid_history_matching():
    """Test that tracks logged with youtube_video_id are also recognized as hard-buffered by UUID."""
    import uuid
    token = f"pytest_dual_key_{uuid.uuid4()}"
    mgr = SessionManager()
    session = mgr.get_or_create_session(token)

    # Log by UUID with video ID
    mgr.record_feedback(token, "track_uuid_12345", "COMPLETED", youtube_video_id="yt_vid_abcde")

    # Both must be hard-buffered
    assert session.is_hard_buffered("track_uuid_12345", "yt_vid_abcde")
    assert session.is_hard_buffered("other_uuid", "yt_vid_abcde")
    assert session.is_hard_buffered("track_uuid_12345", "other_vid")

def test_heard_tracks_never_reappear_within_50_steps():
    """Test that a completed track is hard-buffered for up to 50 steps."""
    import uuid
    token = f"pytest_50_step_{uuid.uuid4()}"
    mgr = SessionManager()
    session = mgr.get_or_create_session(token)

    mgr.record_feedback(token, "heard_track_001", "COMPLETED", youtube_video_id="yt_001")
    assert session.is_hard_buffered("heard_track_001")

    # Simulate playing 40 other tracks (within 50-step buffer)
    for i in range(40):
        mgr.record_feedback(token, f"filler_{i}", "COMPLETED", youtube_video_id=f"yt_filler_{i}")

    # Must still be hard buffered!
    assert session.is_hard_buffered("heard_track_001")

def test_session_history_endpoints_and_clear():
    """Test GET and DELETE /api/v1/sessions/{token}/history endpoints."""
    with TestClient(app) as test_client:
        import uuid
        token = f"pytest_history_api_{uuid.uuid4()}"

        # Record 2 feedback events
        test_client.post("/api/v1/sessions/feedback", json={
            "session_token": token,
            "track_id": "track_hist_1",
            "youtube_video_id": "yt_hist_1",
            "event_type": "COMPLETED",
            "listen_duration_seconds": 180
        })
        test_client.post("/api/v1/sessions/feedback", json={
            "session_token": token,
            "track_id": "track_hist_2",
            "youtube_video_id": "yt_hist_2",
            "event_type": "SKIPPED",
            "listen_duration_seconds": 15
        })

        # Fetch history
        res = test_client.get(f"/api/v1/sessions/{token}/history")
        assert res.status_code == 200
        hist_data = res.json()
        assert hist_data["count"] >= 2
        events = [h["event_type"] for h in hist_data["history"]]
        assert "COMPLETED" in events
        assert "SKIPPED" in events

        # Clear history
        del_res = test_client.delete(f"/api/v1/sessions/{token}/history")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "cleared"

        # Verify history is now empty
        res_after = test_client.get(f"/api/v1/sessions/{token}/history")
        assert res_after.status_code == 200
        assert res_after.json()["count"] == 0




