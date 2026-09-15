"""
Database Migration & Seeding Engine.
Migrates legacy YAML/JSON starred tracks and seeds authentic Amharic tracks into SQLite.
"""
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List
from .database import init_db, get_db_path
from .repository import track_repo, vault_repo
from ..seed_catalog import AMHARIC_SEED_TRACKS, generate_amharic_seed_catalog

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"

def migrate_legacy_starred_files() -> int:
    """
    Reads data/starred.json and data/starred.yaml (if present) and imports
    them into SQLite liked_tracks table without duplicating records.
    """
    yaml_path = DATA_DIR / "starred.yaml"
    json_path = DATA_DIR / "starred.json"
    root_json_path = Path(__file__).resolve().parent.parent.parent.parent / "acoustic_vault_favorites.json"
    imported_count = 0
    seen_ids = set()

    tracks_to_import: List[Dict[str, Any]] = []

    # 1. Read from YAML
    if yaml_path.exists():
        try:
            with open(yaml_path, "r", encoding="utf-8") as yf:
                data = yaml.safe_load(yf)
                if data and "starred_tracks" in data:
                    for t in data["starred_tracks"]:
                        tid = t.get("track_id") or t.get("youtube_video_id")
                        if tid and tid not in seen_ids:
                            seen_ids.add(tid)
                            tracks_to_import.append(t)
        except Exception as e:
            print(f"⚠️ Error reading legacy YAML starred file: {e}")

    # 2. Read from JSON in data/
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as jf:
                data = json.load(jf)
                items = data.get("starred_tracks", data if isinstance(data, list) else [])
                for t in items:
                    tid = t.get("track_id") or t.get("youtube_video_id")
                    if tid and tid not in seen_ids:
                        seen_ids.add(tid)
                        tracks_to_import.append(t)
        except Exception as e:
            print(f"⚠️ Error reading legacy JSON starred file: {e}")

    # 3. Read from root exported acoustic_vault_favorites.json
    if root_json_path.exists():
        try:
            with open(root_json_path, "r", encoding="utf-8") as rf:
                data = json.load(rf)
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get("starred_tracks", [])
                else:
                    items = []
                for t in items:
                    tid = t.get("track_id") or t.get("youtube_video_id")
                    if tid and tid not in seen_ids:
                        seen_ids.add(tid)
                        tracks_to_import.append(t)
        except Exception as e:
            print(f"⚠️ Error reading acoustic_vault_favorites.json: {e}")



    # 3. Insert into SQLite liked_tracks
    for t in tracks_to_import:
        track_dict = {
            "track_id": t.get("track_id") or f"track_{t.get('youtube_video_id')}",
            "youtube_video_id": t.get("youtube_video_id", ""),
            "title": t.get("title", "Unknown Title"),
            "channel_name": t.get("channel_name", "Unknown Artist"),
            "qenet_mode": t.get("qenet_mode", "Tizita"),
            "era": t.get("era", "Golden 70s"),
            "bpm": float(t.get("bpm", 100.0)),
            "duration_seconds": int(t.get("duration_seconds", 240)),
            "user_notes": t.get("user_notes", None)
        }
        vault_repo.add_liked_track(track_dict)
        imported_count += 1

    if imported_count > 0:
        print(f"📥 Successfully migrated {imported_count} starred tracks from legacy JSON/YAML to SQLite.")
    return imported_count

def seed_sqlite_catalog() -> int:
    """
    Seeds all authentic Amharic tracks with Qenet scales and 2D SVD coordinates into SQLite.
    """
    tracks = generate_amharic_seed_catalog()
    track_dicts = []
    for t in tracks:
        track_dicts.append({
            "track_id": t.track_id,
            "youtube_video_id": t.youtube_video_id,
            "title": t.title,
            "channel_name": t.channel_name,
            "duration_seconds": t.duration_seconds,
            "view_count": t.view_count,
            "genre_tags": t.genre_tags,
            "era": t.era,
            "qenet_mode": t.acoustic_features.qenet_mode,
            "qenet_submode": t.acoustic_features.qenet_submode,
            "qenet_confidence": t.acoustic_features.qenet_confidence,
            "bpm": t.acoustic_features.bpm,
            "energy": t.acoustic_features.energy,
            "brightness": t.acoustic_features.brightness,
            "danceability": t.acoustic_features.danceability,
            "tonal_energy": t.acoustic_features.tonal_energy,
            "harmonic_key": t.acoustic_features.harmonic_key,
            "galaxy_x": t.galaxy_x,
            "galaxy_y": t.galaxy_y
        })
    count = track_repo.bulk_upsert_tracks(track_dicts)
    print(f"🇪🇹 Populated SQLite 'tracks' table with {count} verified Ethiopian tracks.")
    
    # Also sync any existing Qdrant catalog tracks into SQLite if available
    try:
        from ..services.vector_store import vector_store
        results, _ = vector_store.client.scroll(
            collection_name=vector_store.collection_name,
            limit=1000,
            with_payload=True
        )
        if results:
            qdrant_track_dicts = []
            for p in results:
                pl = p.payload or {}
                qdrant_track_dicts.append({
                    "track_id": pl.get("track_id", str(p.id)),
                    "youtube_video_id": pl.get("youtube_video_id", ""),
                    "title": pl.get("title", "Unknown Title"),
                    "channel_name": pl.get("channel_name", "Unknown Artist"),
                    "duration_seconds": pl.get("duration_seconds", 240),
                    "view_count": pl.get("view_count", 1000),
                    "genre_tags": pl.get("genre_tags", []),
                    "era": pl.get("era", "Modern"),
                    "qenet_mode": pl.get("qenet_mode", "Tizita"),
                    "qenet_submode": pl.get("qenet_submode", "Tizita Major"),
                    "qenet_confidence": pl.get("qenet_confidence", 0.8),
                    "bpm": pl.get("bpm", 100.0),
                    "energy": pl.get("energy", 0.5),
                    "brightness": pl.get("brightness", 0.5),
                    "danceability": pl.get("danceability", 0.5),
                    "tonal_energy": pl.get("tonal_energy", 0.5),
                    "harmonic_key": pl.get("harmonic_key", "C"),
                    "galaxy_x": pl.get("galaxy_x", 0.0),
                    "galaxy_y": pl.get("galaxy_y", 0.0)
                })
            if qdrant_track_dicts:
                q_count = track_repo.bulk_upsert_tracks(qdrant_track_dicts)
                print(f"🔄 Synced {q_count} tracks from Qdrant vector store into SQLite.")
                count = q_count
    except Exception as e:
        print(f"⚠️ Qdrant to SQLite sync notice: {e}")

    return count

def run_all_migrations():
    """Entrypoint to initialize SQLite schema, seed tracks, and migrate legacy starred files."""
    init_db()
    seed_sqlite_catalog()
    migrate_legacy_starred_files()
    print("✅ SQLite database initialization & migrations complete.")

if __name__ == "__main__":
    run_all_migrations()

