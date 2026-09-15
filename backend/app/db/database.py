"""
SQLite Database Connection & Schema Management.
Stores indexed tracks, user favorites (liked tracks), playback history, and sessions.
"""
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
DB_PATH = DATA_DIR / "recommender.db"

def get_db_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DB_PATH

@contextmanager
def get_db_connection(db_path: Path = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for thread-safe SQLite connection with WAL mode and foreign keys enabled.
    """
    target_path = db_path or get_db_path()
    conn = sqlite3.connect(
        str(target_path),
        timeout=10.0,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: Path = None):
    """
    Initializes SQLite tables for tracks, liked_tracks, playback_history, and sessions.
    """
    target_path = db_path or get_db_path()
    with get_db_connection(target_path) as conn:
        cursor = conn.cursor()
        
        # 1. Tracks Table (Catalog & Audio Features)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            track_id TEXT PRIMARY KEY,
            youtube_video_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            channel_name TEXT NOT NULL,
            duration_seconds INTEGER DEFAULT 240,
            view_count INTEGER DEFAULT 0,
            genre_tags TEXT DEFAULT '[]',
            era TEXT DEFAULT 'Golden 70s',
            qenet_mode TEXT DEFAULT 'Tizita',
            qenet_submode TEXT DEFAULT 'Tizita Minor',
            qenet_confidence REAL DEFAULT 0.85,
            bpm REAL DEFAULT 100.0,
            energy REAL DEFAULT 0.5,
            brightness REAL DEFAULT 0.5,
            danceability REAL DEFAULT 0.5,
            tonal_energy REAL DEFAULT 0.5,
            harmonic_key TEXT DEFAULT 'C',
            galaxy_x REAL DEFAULT 0.0,
            galaxy_y REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 2. Liked Tracks Table (My Vault Favorites)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS liked_tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id TEXT NOT NULL,
            youtube_video_id TEXT NOT NULL,
            title TEXT,
            channel_name TEXT,
            qenet_mode TEXT DEFAULT 'Tizita',
            era TEXT DEFAULT 'Golden 70s',
            bpm REAL DEFAULT 100.0,
            duration_seconds INTEGER DEFAULT 240,
            user_notes TEXT,
            starred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(track_id),
            UNIQUE(youtube_video_id)
        );
        """)
        
        # 3. Playback History Table (Heard & Interaction Events)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS playback_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_token TEXT NOT NULL,
            track_id TEXT NOT NULL,
            youtube_video_id TEXT,
            event_type TEXT NOT NULL, -- COMPLETED, SKIPPED, DISLIKED, STARRED
            listen_duration_seconds INTEGER DEFAULT 0,
            step_index INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_session ON playback_history(session_token);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_track ON playback_history(track_id);")

        # 4. Sessions Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_token TEXT PRIMARY KEY,
            current_step INTEGER DEFAULT 0,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            taste_centroid TEXT, -- JSON serialized vector
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
