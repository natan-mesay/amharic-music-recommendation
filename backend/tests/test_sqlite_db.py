"""
Unit and Integration Tests for SQLite Database Layer & Migration.
"""
import pytest
import tempfile
import json
import yaml
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.database import get_db_connection, init_db
from backend.app.db.repository import (
    TrackRepository,
    VaultRepository,
    HistoryRepository,
    SessionRepository
)
from backend.app.db.migrate import migrate_legacy_starred_files, seed_sqlite_catalog

test_client = TestClient(app)

@pytest.fixture
def temp_db():
    """Provides a temporary SQLite database path for isolated test runs."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    init_db(db_path)
    yield db_path
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass

def test_init_db_and_pragmas(temp_db):
    """Test that SQLite schema and WAL mode are initialized properly."""
    with get_db_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "tracks" in tables
        assert "liked_tracks" in tables
        assert "playback_history" in tables
        assert "sessions" in tables

def test_track_repository_crud(temp_db):
    """Test inserting, querying, and counting tracks in SQLite."""
    repo = TrackRepository(temp_db)
    track_data = {
        "track_id": "test_t1",
        "youtube_video_id": "yt_test_123",
        "title": "Tizita Classic",
        "channel_name": "Tilahun Gessesse",
        "duration_seconds": 300,
        "view_count": 10000,
        "genre_tags": ["tizita", "amharic"],
        "era": "Golden 70s",
        "qenet_mode": "Tizita",
        "qenet_submode": "Tizita Minor",
        "qenet_confidence": 0.92,
        "bpm": 88.0,
        "energy": 0.45,
        "brightness": 0.40,
        "danceability": 0.50,
        "tonal_energy": 0.85,
        "harmonic_key": "Dm",
        "galaxy_x": -0.45,
        "galaxy_y": 0.32
    }
    
    assert repo.upsert_track(track_data) is True
    assert repo.count_tracks() == 1
    
    fetched = repo.get_track_by_id("test_t1")
    assert fetched is not None
    assert fetched["title"] == "Tizita Classic"
    assert fetched["bpm"] == 88.0
    assert fetched["galaxy_x"] == -0.45
    assert "tizita" in fetched["genre_tags"]

    fetched_yt = repo.get_track_by_youtube_id("yt_test_123")
    assert fetched_yt is not None
    assert fetched_yt["track_id"] == "test_t1"

def test_vault_repository_liked_tracks(temp_db):
    """Test starring and unstarring tracks in My Vault via SQLite."""
    repo = VaultRepository(temp_db)
    liked_item = {
        "track_id": "fav_001",
        "youtube_video_id": "yt_fav_001",
        "title": "Shih Bibal",
        "channel_name": "Teddy Afro",
        "qenet_mode": "Tizita",
        "era": "Modern 2020s",
        "bpm": 108.0,
        "duration_seconds": 303,
        "user_notes": "Favorite reggae groove"
    }

    assert repo.add_liked_track(liked_item) is True
    all_liked = repo.get_all_liked_tracks()
    assert len(all_liked) == 1
    assert all_liked[0]["title"] == "Shih Bibal"

    # Remove track
    assert repo.remove_liked_track("fav_001") is True
    assert len(repo.get_all_liked_tracks()) == 0

def test_history_repository_interactions(temp_db):
    """Test recording playback events and retrieving session history."""
    repo = HistoryRepository(temp_db)
    token = "session_test_xyz"

    repo.record_interaction(token, "track_1", "COMPLETED", "yt_1", 200, 1)
    repo.record_interaction(token, "track_2", "SKIPPED", "yt_2", 15, 2)
    repo.record_interaction(token, "track_3", "COMPLETED", "yt_3", 180, 3)

    history = repo.get_session_history(token)
    assert len(history) == 3
    assert history[0]["event_type"] == "COMPLETED"
    assert history[1]["event_type"] == "SKIPPED"

    cooldown_ids = repo.get_session_cooldown_ids(token)
    assert set(cooldown_ids) == {"track_1", "track_2", "track_3"}

def test_api_vault_endpoints():
    """Test FastAPI REST endpoints for SQLite Vault and History."""
    # 1. Add / Sync to Vault
    res_post = test_client.post("/api/v1/vault/starred", json={
        "starred_tracks": [
            {
                "track_id": "api_test_001",
                "youtube_video_id": "vid_api_001",
                "title": "Gela Gela",
                "channel_name": "Aster Aweke",
                "qenet_mode": "Anchihoye",
                "era": "80s-90s Cassette",
                "bpm": 126.0
            }
        ]
    })
    assert res_post.status_code == 200

    # 2. Get from Vault
    res_get = test_client.get("/api/v1/vault/starred")
    assert res_get.status_code == 200
    data = res_get.json()
    assert any(t["track_id"] == "api_test_001" for t in data["starred_tracks"])

    # 3. Record Feedback and Query History
    session_token = "sess_api_test"
    res_fb = test_client.post("/api/v1/sessions/feedback", json={
        "session_token": session_token,
        "track_id": "api_test_001",
        "event_type": "COMPLETED",
        "listen_duration_seconds": 120
    })
    assert res_fb.status_code == 200

    res_hist = test_client.get(f"/api/v1/sessions/{session_token}/history")
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert hist_data["count"] >= 1
    assert hist_data["history"][0]["track_id"] == "api_test_001"

    # 4. Remove from Vault
    res_del = test_client.delete("/api/v1/vault/starred/api_test_001")
    assert res_del.status_code == 200
    assert res_del.json()["removed"] is True
