"""
Ephemeral Session Manager for Zero-Replay Cooldown Tracking.
Maintains session state without requiring user login or persistent PII.
"""
import time
from typing import Dict, Set, Optional, List
from pydantic import BaseModel, Field

class SessionState:
    def __init__(self, session_token: str):
        self.session_token = session_token
        self.played_track_ids: Set[str] = set()
        self.skipped_track_ids: Set[str] = set()
        self.disliked_track_ids: Set[str] = set()
        self.seed_history: List[str] = []
        self.last_activity: float = time.time()

    def mark_event(self, track_id: str, event_type: str):
        self.last_activity = time.time()
        if event_type == "COMPLETED" or event_type == "PLAY_COMPLETED":
            self.played_track_ids.add(track_id)
        elif event_type == "SKIPPED" or event_type == "SKIPPED_EARLY":
            self.skipped_track_ids.add(track_id)
        elif event_type == "DISLIKED":
            self.disliked_track_ids.add(track_id)

    def is_in_cooldown(self, track_id: str) -> bool:
        return (
            track_id in self.played_track_ids
            or track_id in self.skipped_track_ids
            or track_id in self.disliked_track_ids
        )

    def get_all_cooldown_ids(self) -> Set[str]:
        return self.played_track_ids | self.skipped_track_ids | self.disliked_track_ids

class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}

    def get_or_create_session(self, session_token: str) -> SessionState:
        # Clean up stale sessions (older than 24h)
        now = time.time()
        stale_keys = [k for k, v in self._sessions.items() if now - v.last_activity > 86400]
        for k in stale_keys:
            del self._sessions[k]

        if session_token not in self._sessions:
            self._sessions[session_token] = SessionState(session_token)
        return self._sessions[session_token]

    def record_feedback(self, session_token: str, track_id: str, event_type: str):
        session = self.get_or_create_session(session_token)
        session.mark_event(track_id, event_type)
        return session

session_manager = SessionManager()
