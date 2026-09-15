"""
Session Manager with SQLite Persistence and Controlled Soft Fatigue Decay.
Maintains session interaction history, immediate hard buffers, and exponential recency decay.
"""
import time
import math
from typing import Dict, Set, Optional, List, NamedTuple
from ..db.repository import history_repo, session_repo, vault_repo

class InteractionRecord(NamedTuple):
    last_index: int
    event_type: str
    timestamp: float

class SessionState:
    def __init__(self, session_token: str):
        self.session_token = session_token
        self.current_step: int = 0
        self.history: Dict[str, InteractionRecord] = {}
        self.history_by_vid: Dict[str, InteractionRecord] = {}
        self.disliked_track_ids: Set[str] = set()
        self.disliked_video_ids: Set[str] = set()
        self.liked_track_ids: Set[str] = set()
        self.liked_video_ids: Set[str] = set()
        self.all_time_heard_ids: Set[str] = set()
        self.all_time_heard_vids: Set[str] = set()
        self.seed_history: List[str] = []
        self.last_activity: float = time.time()

        # Robust fatigue parameters (50-track continuous discovery cooldown)
        self.K_COMPLETED = 50       # Immediate hard buffer for completed songs (covers ~70% of catalog)
        self.TAU_COMPLETED = 40.0   # Exponential decay scale
        self.GAMMA_COMPLETED = 0.60 # Peak fatigue penalty

        self.K_SKIPPED = 60         # Immediate hard buffer for skipped songs
        self.TAU_SKIPPED = 80.0     # Exponential decay scale
        self.GAMMA_SKIPPED = 0.95   # Peak fatigue penalty

        # 1. Hydrate liked tracks from SQLite Vault
        try:
            liked = vault_repo.get_all_liked_tracks()
            self.liked_track_ids = {t["track_id"] for t in liked if t.get("track_id")}
            self.liked_video_ids = {t["youtube_video_id"] for t in liked if t.get("youtube_video_id")}
        except Exception:
            pass

        # 2. Hydrate all-time heard history across all sessions from SQLite
        try:
            all_time = history_repo.get_all_time_heard_ids()
            self.all_time_heard_ids = all_time["track_ids"]
            self.all_time_heard_vids = all_time["youtube_video_ids"]
        except Exception:
            pass

    def mark_event(self, track_id: str, event_type: str, youtube_video_id: Optional[str] = None, duration_sec: int = 0):
        self.last_activity = time.time()
        self.current_step += 1
        
        normalized_event = event_type.upper()
        if "DISLIKE" in normalized_event:
            self.disliked_track_ids.add(track_id)
            if youtube_video_id: self.disliked_video_ids.add(youtube_video_id)
            self.liked_track_ids.discard(track_id)
            if youtube_video_id: self.liked_video_ids.discard(youtube_video_id)
        elif "LIKE" in normalized_event or "STAR" in normalized_event or "BOOKMARK" in normalized_event:
            self.liked_track_ids.add(track_id)
            if youtube_video_id: self.liked_video_ids.add(youtube_video_id)
            self.disliked_track_ids.discard(track_id)
            if youtube_video_id: self.disliked_video_ids.discard(youtube_video_id)
        elif "UNSTAR" in normalized_event or "UNLIKE" in normalized_event:
            self.liked_track_ids.discard(track_id)
            if youtube_video_id: self.liked_video_ids.discard(youtube_video_id)
        
        record = InteractionRecord(
            last_index=self.current_step,
            event_type=normalized_event,
            timestamp=self.last_activity
        )
        self.history[track_id] = record
        if youtube_video_id:
            self.history_by_vid[youtube_video_id] = record
            self.all_time_heard_vids.add(youtube_video_id)
        self.all_time_heard_ids.add(track_id)

        # Persist to SQLite
        try:
            history_repo.record_interaction(
                session_token=self.session_token,
                track_id=track_id,
                event_type=normalized_event,
                youtube_video_id=youtube_video_id,
                duration_sec=duration_sec,
                step_index=self.current_step
            )
            session_repo.upsert_session(
                session_token=self.session_token,
                current_step=self.current_step
            )
        except Exception as e:
            print(f"⚠️ SQLite history logging warning: {e}")

    def sync_vault(self, liked_ids: List[str]):
        self.last_activity = time.time()
        self.liked_track_ids = set(liked_ids)

    def get_taste_centroid(self, vector_store) -> Optional[List[float]]:
        """
        Computes the acoustic centroid (average sound vector) of all user-liked tracks.
        """
        if not self.liked_track_ids:
            return None
        
        vectors = []
        for tid in self.liked_track_ids:
            t = vector_store.get_track_by_id(tid)
            if t and "acoustic_features" in t and "embedding" in t["acoustic_features"]:
                vectors.append(t["acoustic_features"]["embedding"])
        
        if not vectors:
            return None
        
        import numpy as np
        centroid = np.mean(vectors, axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm
        return centroid.tolist()

    def is_all_time_heard(self, track_id: str, youtube_video_id: Optional[str] = None) -> bool:
        """Check if track has ever been played in any session."""
        if track_id in self.all_time_heard_ids:
            return True
        if youtube_video_id and youtube_video_id in self.all_time_heard_vids:
            return True
        return False

    def is_hard_buffered(self, track_id: str, youtube_video_id: Optional[str] = None) -> bool:
        """
        Check if track is currently strictly blocked (Disliked or within immediate K buffer).
        Supports dual-key check with track_id and youtube_video_id.
        """
        if track_id in self.disliked_track_ids:
            return True
        if youtube_video_id and youtube_video_id in self.disliked_video_ids:
            return True

        record = self.history.get(track_id)
        if not record and youtube_video_id:
            record = self.history_by_vid.get(youtube_video_id)

        if not record:
            return False

        distance = self.current_step - record.last_index
        ev = record.event_type.upper()
        if "UNAVAILABLE" in ev or "EMBED_RESTRICTED" in ev:
            return distance <= 3  # Short buffer for broken tracks
        elif "SKIP" in ev:
            return distance <= self.K_SKIPPED
        else:
            return distance <= self.K_COMPLETED

    def get_fatigue_penalty(self, track_id: str, youtube_video_id: Optional[str] = None) -> float:
        """
        Computes the soft fatigue penalty Penalty(t) in [0.0, 1.0].
        Penalty is 1.0 for hard buffers, decaying exponentially as play distance increases.
        """
        if track_id in self.disliked_track_ids or (youtube_video_id and youtube_video_id in self.disliked_video_ids):
            return 1.0

        record = self.history.get(track_id)
        if not record and youtube_video_id:
            record = self.history_by_vid.get(youtube_video_id)

        if not record:
            return 0.0

        distance = self.current_step - record.last_index
        ev = record.event_type.upper()

        if "UNAVAILABLE" in ev or "EMBED_RESTRICTED" in ev:
            return 0.0 if distance > 3 else 1.0

        if "SKIP" in ev:
            k = self.K_SKIPPED
            tau = self.TAU_SKIPPED
            gamma = self.GAMMA_SKIPPED
        else:
            k = self.K_COMPLETED
            tau = self.TAU_COMPLETED
            gamma = self.GAMMA_COMPLETED

        if distance <= k:
            return 1.0

        # Soft exponential decay: gamma * exp(-(distance - k) / tau)
        excess_distance = distance - k
        decayed_penalty = gamma * math.exp(-excess_distance / tau)
        return float(max(0.0, min(1.0, decayed_penalty)))

    def get_active_cooldown_count(self) -> int:
        """Returns total tracks currently in hard buffer or disliked."""
        count = len(self.disliked_track_ids)
        for t_id, record in self.history.items():
            if t_id not in self.disliked_track_ids and self.is_hard_buffered(t_id):
                count += 1
        return count

    def get_all_cooldown_ids(self) -> Set[str]:
        """Returns set of all currently hard-buffered track IDs."""
        buffered = set(self.disliked_track_ids)
        for t_id in self.history:
            if self.is_hard_buffered(t_id):
                buffered.add(t_id)
        for v_id in self.history_by_vid:
            if self.is_hard_buffered(v_id, v_id):
                buffered.add(v_id)
        return buffered


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}

    def get_or_create_session(self, session_token: str) -> SessionState:
        now = time.time()
        stale_keys = [k for k, v in self._sessions.items() if now - v.last_activity > 86400]
        for k in stale_keys:
            del self._sessions[k]

        if session_token not in self._sessions:
            state = SessionState(session_token)
            # Rehydrate from SQLite if history exists
            try:
                hist = history_repo.get_session_history(session_token)
                for h in hist:
                    state.current_step = max(state.current_step, h["step_index"])
                    ev = h["event_type"].upper()
                    tid = h["track_id"]
                    vid = h.get("youtube_video_id")
                    if "DISLIKE" in ev:
                        state.disliked_track_ids.add(tid)
                        if vid: state.disliked_video_ids.add(vid)
                    elif "LIKE" in ev or "STAR" in ev:
                        state.liked_track_ids.add(tid)
                        if vid: state.liked_video_ids.add(vid)
                    
                    rec = InteractionRecord(
                        last_index=h["step_index"],
                        event_type=ev,
                        timestamp=time.time()
                    )
                    state.history[tid] = rec
                    if vid:
                        state.history_by_vid[vid] = rec
            except Exception:
                pass
            self._sessions[session_token] = state
        return self._sessions[session_token]

    def record_feedback(self, session_token: str, track_id: str, event_type: str, youtube_video_id: Optional[str] = None, duration_sec: int = 0):
        session = self.get_or_create_session(session_token)
        session.mark_event(track_id, event_type, youtube_video_id=youtube_video_id, duration_sec=duration_sec)
        return session

    def clear_session(self, session_token: str):
        if session_token in self._sessions:
            del self._sessions[session_token]
        history_repo.clear_session_history(session_token)

session_manager = SessionManager()

