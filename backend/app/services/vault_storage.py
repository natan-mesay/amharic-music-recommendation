import json
import os
from pathlib import Path
from typing import List, Dict, Any
import yaml

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
STARRED_YAML_PATH = DATA_DIR / "starred.yaml"
STARRED_JSON_PATH = DATA_DIR / "starred.json"

class VaultStorage:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.yaml_path = self.data_dir / "starred.yaml"
        self.json_path = self.data_dir / "starred.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save_starred(self, tracks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Persist starred tracks to both starred.yaml and starred.json on disk."""
        data_payload = {
            "version": "1.0",
            "total_starred": len(tracks),
            "starred_tracks": tracks
        }
        
        # 1. Save to starred.yaml
        with open(self.yaml_path, "w", encoding="utf-8") as yf:
            yaml.dump(data_payload, yf, default_flow_style=False, allow_unicode=True, sort_keys=False)

        # 2. Save to starred.json
        with open(self.json_path, "w", encoding="utf-8") as jf:
            json.dump(data_payload, jf, indent=2, ensure_ascii=False)

        return {
            "status": "success",
            "count": len(tracks),
            "yaml_file": str(self.yaml_path),
            "json_file": str(self.json_path)
        }

    def get_starred(self) -> List[Dict[str, Any]]:
        """Load persisted starred tracks from YAML or JSON file."""
        if self.yaml_path.exists():
            try:
                with open(self.yaml_path, "r", encoding="utf-8") as yf:
                    data = yaml.safe_load(yf)
                    if data and "starred_tracks" in data:
                        return data["starred_tracks"]
            except Exception:
                pass

        if self.json_path.exists():
            try:
                with open(self.json_path, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                    if data and "starred_tracks" in data:
                        return data["starred_tracks"]
            except Exception:
                pass

        return []

vault_storage = VaultStorage()
