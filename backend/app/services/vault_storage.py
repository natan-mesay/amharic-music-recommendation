"""
Vault Storage Service backed by persistent SQLite Database.
Provides CRUD and M3U playlist export functions.
"""
from typing import List, Dict, Any
from pathlib import Path
from ..db.repository import vault_repo

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"

class VaultStorage:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.repo = vault_repo

    def save_starred(self, tracks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Persist starred tracks directly to SQLite liked_tracks table."""
        count = self.repo.sync_liked_tracks_batch(tracks)
        return {
            "status": "success",
            "count": count,
            "database": "SQLite (data/recommender.db)"
        }

    def get_starred(self) -> List[Dict[str, Any]]:
        """Load starred tracks directly from SQLite liked_tracks table."""
        return self.repo.get_all_liked_tracks()

    def add_track(self, track: Dict[str, Any]) -> bool:
        return self.repo.add_liked_track(track)

    def remove_track(self, identifier: str) -> bool:
        return self.repo.remove_liked_track(identifier)

    def clear_vault(self):
        self.repo.clear_vault()

vault_storage = VaultStorage()
