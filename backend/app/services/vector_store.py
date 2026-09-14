"""
Vector Database Storage and Similarity Search using Qdrant (Local / In-Memory / File Persistent).
"""
import os
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, Range
from ..config import settings, QDRANT_STORAGE_PATH
from ..models.schemas import Track

import uuid

def to_valid_uuid(id_str: str) -> str:
    """Ensure an ID string is a valid UUID4/UUID5 format for Qdrant."""
    try:
        return str(uuid.UUID(id_str))
    except (ValueError, AttributeError):
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(id_str)))

class VectorStore:
    def __init__(self, in_memory: bool = False):
        if in_memory:
            self.client = QdrantClient(":memory:")
        else:
            try:
                self.client = QdrantClient(path=QDRANT_STORAGE_PATH)
            except Exception:
                self.client = QdrantClient(":memory:")
        self.collection_name = settings.COLLECTION_NAME
        self._ensure_collection()

    def _ensure_collection(self):
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIM,
                    distance=Distance.COSINE
                )
            )

    def upsert_track(self, track: Track) -> bool:
        """
        Store track embedding vector and rich metadata payload into Qdrant.
        """
        point_id = to_valid_uuid(track.track_id)
        point = PointStruct(
            id=point_id,
            vector=track.acoustic_features.embedding,
            payload={
                "track_id": track.track_id,
                "youtube_video_id": track.youtube_video_id,
                "title": track.title,
                "channel_name": track.channel_name,
                "duration_seconds": track.duration_seconds,
                "view_count": track.view_count,
                "genre_tags": track.genre_tags,
                "bpm": track.acoustic_features.bpm,
                "energy": track.acoustic_features.energy,
                "brightness": track.acoustic_features.brightness,
                "danceability": track.acoustic_features.danceability,
                "tonal_energy": track.acoustic_features.tonal_energy,
                "harmonic_key": track.acoustic_features.harmonic_key
            }
        )
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        return True

    def upsert_tracks_batch(self, tracks: List[Track]) -> int:
        points = []
        for track in tracks:
            point_id = to_valid_uuid(track.track_id)
            points.append(
                PointStruct(
                    id=point_id,
                    vector=track.acoustic_features.embedding,
                    payload={
                        "track_id": track.track_id,
                        "youtube_video_id": track.youtube_video_id,
                        "title": track.title,
                        "channel_name": track.channel_name,
                        "duration_seconds": track.duration_seconds,
                        "view_count": track.view_count,
                        "genre_tags": track.genre_tags,
                        "bpm": track.acoustic_features.bpm,
                        "energy": track.acoustic_features.energy,
                        "brightness": track.acoustic_features.brightness,
                        "danceability": track.acoustic_features.danceability,
                        "tonal_energy": track.acoustic_features.tonal_energy,
                        "harmonic_key": track.acoustic_features.harmonic_key
                    }
                )
            )
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        return len(points)

    def search_similar(
        self,
        query_vector: List[float],
        limit: int = 50,
        min_bpm: Optional[float] = None,
        max_bpm: Optional[float] = None,
        min_duration_sec: Optional[int] = None,
        max_duration_sec: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Cosine vector similarity query with optional acoustic & duration filters.
        """
        must_filters = []
        
        if min_bpm is not None or max_bpm is not None:
            bpm_range = Range(
                gte=min_bpm if min_bpm is not None else None,
                lte=max_bpm if max_bpm is not None else None
            )
            must_filters.append(FieldCondition(key="bpm", range=bpm_range))
            
        if min_duration_sec is not None or max_duration_sec is not None:
            dur_range = Range(
                gte=min_duration_sec if min_duration_sec is not None else None,
                lte=max_duration_sec if max_duration_sec is not None else None
            )
            must_filters.append(FieldCondition(key="duration_seconds", range=dur_range))
            
        qdrant_filter = Filter(must=must_filters) if must_filters else None

        # Query Qdrant
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True
        )
        
        candidates = []
        for point in results.points:
            candidates.append({
                "track_id": point.payload["track_id"],
                "youtube_video_id": point.payload["youtube_video_id"],
                "title": point.payload["title"],
                "channel_name": point.payload["channel_name"],
                "duration_seconds": point.payload["duration_seconds"],
                "view_count": point.payload["view_count"],
                "genre_tags": point.payload.get("genre_tags", []),
                "bpm": point.payload["bpm"],
                "energy": point.payload["energy"],
                "brightness": point.payload["brightness"],
                "danceability": point.payload.get("danceability", 0.5),
                "similarity_score": point.score
            })
        return candidates

    def get_track_by_id(self, track_id: str) -> Optional[Dict[str, Any]]:
        point_id = to_valid_uuid(track_id)
        points = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[point_id],
            with_payload=True,
            with_vectors=True
        )
        if points:
            p = points[0]
            return {
                "track_id": p.payload["track_id"],
                "youtube_video_id": p.payload["youtube_video_id"],
                "title": p.payload["title"],
                "channel_name": p.payload["channel_name"],
                "duration_seconds": p.payload["duration_seconds"],
                "view_count": p.payload["view_count"],
                "genre_tags": p.payload.get("genre_tags", []),
                "acoustic_features": {
                    "bpm": p.payload["bpm"],
                    "energy": p.payload["energy"],
                    "brightness": p.payload["brightness"],
                    "danceability": p.payload.get("danceability", 0.5),
                    "tonal_energy": p.payload.get("tonal_energy", 0.5),
                    "harmonic_key": p.payload.get("harmonic_key", "C"),
                    "embedding": p.vector
                }
            }
        return None

    def get_track_by_youtube_id(self, youtube_video_id: str) -> Optional[Dict[str, Any]]:
        """Fast-path lookup to find indexed track by YouTube video ID."""
        filter_cond = Filter(must=[FieldCondition(key="youtube_video_id", match=MatchValue(value=youtube_video_id))])
        try:
            results, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=filter_cond,
                limit=1,
                with_payload=True,
                with_vectors=True
            )
            if results:
                p = results[0]
                return {
                    "track_id": p.payload["track_id"],
                    "youtube_video_id": p.payload["youtube_video_id"],
                    "title": p.payload["title"],
                    "channel_name": p.payload["channel_name"],
                    "duration_seconds": p.payload["duration_seconds"],
                    "view_count": p.payload["view_count"],
                    "genre_tags": p.payload.get("genre_tags", []),
                    "acoustic_features": {
                        "bpm": p.payload["bpm"],
                        "energy": p.payload["energy"],
                        "brightness": p.payload["brightness"],
                        "danceability": p.payload.get("danceability", 0.5),
                        "tonal_energy": p.payload.get("tonal_energy", 0.5),
                        "harmonic_key": p.payload.get("harmonic_key", "C"),
                        "embedding": p.vector
                    }
                }
        except Exception:
            pass
        return None

    def get_all_tracks(self, limit: int = 100) -> List[Dict[str, Any]]:
        results, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        return [p.payload for p in results]

    def count_tracks(self) -> int:
        info = self.client.get_collection(self.collection_name)
        return info.points_count or 0

vector_store = VectorStore()
