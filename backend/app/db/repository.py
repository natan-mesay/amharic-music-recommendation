"""
Repository Layer for SQLite Data Access.
Provides typed CRUD methods for Tracks, Liked Tracks, Playback History, and Sessions.
"""
import json
import sqlite3
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from .database import get_db_connection

class TrackRepository:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path

    def upsert_track(self, track_dict: Dict[str, Any]) -> bool:
        """Insert or update a track record."""
        genre_tags = track_dict.get("genre_tags", [])
        if isinstance(genre_tags, list):
            genre_tags_str = json.dumps(genre_tags)
        else:
            genre_tags_str = str(genre_tags)

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO tracks (
                track_id, youtube_video_id, title, channel_name, duration_seconds,
                view_count, genre_tags, era, qenet_mode, qenet_submode, qenet_confidence,
                bpm, energy, brightness, danceability, tonal_energy, harmonic_key,
                galaxy_x, galaxy_y
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(youtube_video_id) DO UPDATE SET
                track_id = excluded.track_id,
                title = excluded.title,
                channel_name = excluded.channel_name,
                duration_seconds = excluded.duration_seconds,
                view_count = excluded.view_count,
                genre_tags = excluded.genre_tags,
                era = excluded.era,
                qenet_mode = excluded.qenet_mode,
                qenet_submode = excluded.qenet_submode,
                qenet_confidence = excluded.qenet_confidence,
                bpm = excluded.bpm,
                energy = excluded.energy,
                brightness = excluded.brightness,
                danceability = excluded.danceability,
                tonal_energy = excluded.tonal_energy,
                harmonic_key = excluded.harmonic_key,
                galaxy_x = excluded.galaxy_x,
                galaxy_y = excluded.galaxy_y;

            """, (
                track_dict["track_id"],
                track_dict["youtube_video_id"],
                track_dict["title"],
                track_dict["channel_name"],
                track_dict.get("duration_seconds", 240),
                track_dict.get("view_count", 0),
                genre_tags_str,
                track_dict.get("era", "Golden 70s"),
                track_dict.get("qenet_mode", "Tizita"),
                track_dict.get("qenet_submode", "Tizita Minor"),
                track_dict.get("qenet_confidence", 0.85),
                track_dict.get("bpm", 100.0),
                track_dict.get("energy", 0.5),
                track_dict.get("brightness", 0.5),
                track_dict.get("danceability", 0.5),
                track_dict.get("tonal_energy", 0.5),
                track_dict.get("harmonic_key", "C"),
                track_dict.get("galaxy_x", 0.0),
                track_dict.get("galaxy_y", 0.0)
            ))
        return True

    def bulk_upsert_tracks(self, tracks: List[Dict[str, Any]]) -> int:
        count = 0
        for t in tracks:
            if self.upsert_track(t):
                count += 1
        return count

    def get_track_by_id(self, track_id: str) -> Optional[Dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tracks WHERE track_id = ?", (track_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                try:
                    d["genre_tags"] = json.loads(d.get("genre_tags", "[]"))
                except Exception:
                    d["genre_tags"] = []
                return d
        return None

    def get_track_by_youtube_id(self, youtube_video_id: str) -> Optional[Dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tracks WHERE youtube_video_id = ?", (youtube_video_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                try:
                    d["genre_tags"] = json.loads(d.get("genre_tags", "[]"))
                except Exception:
                    d["genre_tags"] = []
                return d
        return None

    def get_all_tracks(self, limit: int = 200) -> List[Dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tracks LIMIT ?", (limit,))
            rows = cursor.fetchall()
            results = []
            for row in rows:
                d = dict(row)
                try:
                    d["genre_tags"] = json.loads(d.get("genre_tags", "[]"))
                except Exception:
                    d["genre_tags"] = []
                results.append(d)
            return results

    def get_galaxy_points(self) -> List[Dict[str, Any]]:
        """Retrieve all tracks with their 2D coordinates for Canvas rendering."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT track_id, youtube_video_id, title, channel_name, duration_seconds,
                   view_count, era, qenet_mode, qenet_submode, bpm, energy, brightness,
                   galaxy_x, galaxy_y
            FROM tracks;
            """)
    def update_galaxy_coordinates(self, track_id: str, galaxy_x: float, galaxy_y: float) -> bool:
        """Atomically update 2D Latent Galaxy coordinates for a track."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE tracks
            SET galaxy_x = ?, galaxy_y = ?
            WHERE track_id = ? OR youtube_video_id = ?;
            """, (round(galaxy_x, 4), round(galaxy_y, 4), track_id, track_id))
            return cursor.rowcount > 0

    def batch_update_galaxy_coordinates(self, updates: List[tuple]) -> int:
        """Batch update list of (galaxy_x, galaxy_y, track_id) tuples."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.executemany("""
            UPDATE tracks
            SET galaxy_x = ?, galaxy_y = ?
            WHERE track_id = ? OR youtube_video_id = ?;
            """, [(round(gx, 4), round(gy, 4), tid, tid) for gx, gy, tid in updates])
            return cursor.rowcount

    def count_tracks(self) -> int:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM tracks;")
            return cursor.fetchone()[0]


class VaultRepository:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path

    def add_liked_track(self, track: Dict[str, Any]) -> bool:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO liked_tracks (
                track_id, youtube_video_id, title, channel_name,
                qenet_mode, era, bpm, duration_seconds, user_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(track_id) DO UPDATE SET
                title = excluded.title,
                channel_name = excluded.channel_name,
                qenet_mode = excluded.qenet_mode,
                era = excluded.era,
                bpm = excluded.bpm,
                duration_seconds = excluded.duration_seconds;
            """, (
                track["track_id"],
                track["youtube_video_id"],
                track.get("title", ""),
                track.get("channel_name", ""),
                track.get("qenet_mode", "Tizita"),
                track.get("era", "Golden 70s"),
                track.get("bpm", 100.0),
                track.get("duration_seconds", 240),
                track.get("user_notes", None)
            ))
        return True

    def remove_liked_track(self, identifier: str) -> bool:
        """Remove by track_id or youtube_video_id."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM liked_tracks WHERE track_id = ? OR youtube_video_id = ?;", (identifier, identifier))
            return cursor.rowcount > 0

    def get_all_liked_tracks(self) -> List[Dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT track_id, youtube_video_id, title, channel_name,
                   qenet_mode, era, bpm, duration_seconds, user_notes, starred_at
            FROM liked_tracks
            ORDER BY starred_at DESC;
            """)
            return [dict(r) for r in cursor.fetchall()]

    def sync_liked_tracks_batch(self, tracks: List[Dict[str, Any]]) -> int:
        for t in tracks:
            self.add_liked_track(t)
        return len(tracks)

    def clear_vault(self):
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM liked_tracks;")


class HistoryRepository:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path

    def record_interaction(
        self,
        session_token: str,
        track_id: str,
        event_type: str,
        youtube_video_id: Optional[str] = None,
        duration_sec: int = 0,
        step_index: int = 0
    ) -> bool:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO playback_history (
                session_token, track_id, youtube_video_id, event_type,
                listen_duration_seconds, step_index
            ) VALUES (?, ?, ?, ?, ?, ?);
            """, (session_token, track_id, youtube_video_id, event_type.upper(), duration_sec, step_index))
        return True

    def get_session_history(self, session_token: str, limit: int = 100) -> List[Dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT h.id, h.session_token, h.track_id, h.youtube_video_id, h.event_type,
                   h.listen_duration_seconds, h.step_index, h.created_at,
                   COALESCE(t.title, 'Amharic Track') as title,
                   COALESCE(t.channel_name, 'Acoustic Vault') as channel_name,
                   COALESCE(t.qenet_mode, 'Tizita') as qenet_mode,
                   COALESCE(t.bpm, 100.0) as bpm,
                   COALESCE(t.era, 'Golden 70s') as era
            FROM playback_history h
            LEFT JOIN tracks t ON (h.track_id = t.track_id OR (h.youtube_video_id IS NOT NULL AND h.youtube_video_id = t.youtube_video_id))
            WHERE h.session_token = ?
            ORDER BY h.id DESC
            LIMIT ?;
            """, (session_token, limit))
            return [dict(r) for r in cursor.fetchall()]

    def get_all_time_heard_ids(self) -> Dict[str, Set[str]]:
        """Returns sets of all track_ids and youtube_video_ids ever played across all sessions."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT DISTINCT track_id, youtube_video_id
            FROM playback_history;
            """)
            rows = cursor.fetchall()
            track_ids = set()
            youtube_video_ids = set()
            for r in rows:
                if r[0]: track_ids.add(r[0])
                if r[1]: youtube_video_ids.add(r[1])
            return {"track_ids": track_ids, "youtube_video_ids": youtube_video_ids}

    def get_session_cooldown_ids(self, session_token: str) -> List[str]:
        """Returns list of distinct track IDs played in this session."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT DISTINCT track_id
            FROM playback_history
            WHERE session_token = ?;
            """, (session_token,))
            return [r[0] for r in cursor.fetchall()]

    def clear_session_history(self, session_token: str) -> int:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM playback_history WHERE session_token = ?;", (session_token,))
            return cursor.rowcount


class SessionRepository:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path

    def upsert_session(self, session_token: str, current_step: int = 0, taste_centroid: Optional[List[float]] = None):
        centroid_str = json.dumps(taste_centroid) if taste_centroid is not None else None
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO sessions (session_token, current_step, taste_centroid, last_active)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_token) DO UPDATE SET
                current_step = excluded.current_step,
                taste_centroid = COALESCE(excluded.taste_centroid, sessions.taste_centroid),
                last_active = CURRENT_TIMESTAMP;
            """, (session_token, current_step, centroid_str))

    def get_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_token = ?;", (session_token,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                if d.get("taste_centroid"):
                    try:
                        d["taste_centroid"] = json.loads(d["taste_centroid"])
                    except Exception:
                        pass
                return d
        return None

track_repo = TrackRepository()
vault_repo = VaultRepository()
history_repo = HistoryRepository()
session_repo = SessionRepository()
