"""
Core Recommendation and Anti-Popularity Discovery Engine.
Combines:
- High-dimensional acoustic vector similarity
- Dynamic obscurity scoring (λ slider)
- Stateful zero-replay session cooldowns
- Intra-artist diversification
"""
import math
from typing import List, Optional, Tuple, Dict, Any
from ..config import settings
from ..models.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendationItem,
    Track,
    AcousticFeatures
)
from .vector_store import vector_store
from .session_manager import session_manager

class RecommenderEngine:
    def __init__(self, max_views_normalizer: int = settings.MAX_VIEWS_NORMALIZER):
        self.max_views_normalizer = max_views_normalizer
        self.log_max_views = math.log10(max_views_normalizer + 1)

    def calculate_obscurity_score(self, view_count: int) -> float:
        """
        Computes the Obscurity Index O(t) in [0.0, 1.0].
        Underground / low-view tracks get near 1.0; viral hits get near 0.0.
        """
        log_views = math.log10(max(0, view_count) + 1)
        obscurity = 1.0 - (log_views / self.log_max_views)
        return float(max(0.0, min(1.0, obscurity)))

    def generate_recommendations(self, request: RecommendationRequest) -> RecommendationResponse:
        session = session_manager.get_or_create_session(request.session_token)
        cooldown_ids = session.get_all_cooldown_ids() | set(request.excluded_track_ids)

        # 1. Resolve Seed Track
        active_seed = None
        query_vector = None

        if request.seed_track_id:
            seed_data = vector_store.get_track_by_id(request.seed_track_id)
            if seed_data:
                active_seed = Track(
                    track_id=seed_data["track_id"],
                    youtube_video_id=seed_data["youtube_video_id"],
                    title=seed_data["title"],
                    channel_name=seed_data["channel_name"],
                    duration_seconds=seed_data["duration_seconds"],
                    view_count=seed_data["view_count"],
                    genre_tags=seed_data.get("genre_tags", []),
                    acoustic_features=AcousticFeatures(**seed_data["acoustic_features"])
                )
                query_vector = seed_data["acoustic_features"]["embedding"]
                # Seed is also added to cooldown so it isn't recommended to itself
                cooldown_ids.add(request.seed_track_id)

        # If no seed, choose the highest-obscurity unplayed track or first catalog track
        if query_vector is None:
            all_tracks = vector_store.get_all_tracks(limit=50)
            available = [t for t in all_tracks if t["track_id"] not in cooldown_ids]
            chosen = available[0] if available else (all_tracks[0] if all_tracks else None)
            if chosen:
                full_t = vector_store.get_track_by_id(chosen["track_id"])
                if full_t:
                    active_seed = Track(
                        track_id=full_t["track_id"],
                        youtube_video_id=full_t["youtube_video_id"],
                        title=full_t["title"],
                        channel_name=full_t["channel_name"],
                        duration_seconds=full_t["duration_seconds"],
                        view_count=full_t["view_count"],
                        genre_tags=full_t.get("genre_tags", []),
                        acoustic_features=AcousticFeatures(**full_t["acoustic_features"])
                    )
                    query_vector = full_t["acoustic_features"]["embedding"]
                    cooldown_ids.add(full_t["track_id"])

        if query_vector is None:
            return RecommendationResponse(
                session_token=request.session_token,
                items=[],
                active_seed=None,
                total_candidates_evaluated=0,
                cooldown_count=len(cooldown_ids)
            )

        # 2. Retrieve Nearest Neighbors from Vector DB
        fetch_limit = max(50, request.batch_size * 5)
        raw_candidates = vector_store.search_similar(
            query_vector=query_vector,
            limit=fetch_limit,
            min_bpm=request.min_bpm,
            max_bpm=request.max_bpm,
            min_duration_sec=request.min_duration_sec,
            max_duration_sec=request.max_duration_sec
        )

        # 3. Apply Zero-Replay Cooldowns, Obscurity Weighting & Channel Diversity
        scored_items = []
        channel_counts: Dict[str, int] = {}
        lam = request.obscurity_factor

        for cand in raw_candidates:
            cid = cand["track_id"]
            if cid in cooldown_ids:
                continue

            # Limit consecutive tracks from the exact same channel/artist
            ch_name = cand["channel_name"]
            if channel_counts.get(ch_name, 0) >= 2:
                continue

            sim_score = float(cand.get("similarity_score", 0.0))
            # Rescale cosine score from [-1, 1] to [0, 1] if needed
            norm_sim = max(0.0, min(1.0, (sim_score + 1.0) / 2.0 if sim_score < 0 else sim_score))
            obscurity_score = self.calculate_obscurity_score(cand["view_count"])

            # Composite formula: (1 - λ) * AcousticSim + λ * Obscurity
            composite = (1.0 - lam) * norm_sim + lam * obscurity_score

            item = RecommendationItem(
                track_id=cid,
                youtube_video_id=cand["youtube_video_id"],
                title=cand["title"],
                channel_name=cand["channel_name"],
                duration_seconds=cand["duration_seconds"],
                view_count=cand["view_count"],
                genre_tags=cand.get("genre_tags", []),
                bpm=cand["bpm"],
                energy=cand["energy"],
                brightness=cand["brightness"],
                acoustic_similarity_score=round(norm_sim, 4),
                obscurity_score=round(obscurity_score, 4),
                composite_score=round(composite, 4)
            )
            scored_items.append((composite, item, ch_name))

        # Sort descending by composite discovery score
        scored_items.sort(key=lambda x: x[0], reverse=True)

        # Pick top batch with strict channel diversity
        final_items = []
        for comp, itm, ch in scored_items:
            if len(final_items) >= request.batch_size:
                break
            final_items.append(itm)
            channel_counts[ch] = channel_counts.get(ch, 0) + 1

        return RecommendationResponse(
            session_token=request.session_token,
            items=final_items,
            active_seed=active_seed,
            total_candidates_evaluated=len(raw_candidates),
            cooldown_count=len(cooldown_ids)
        )

recommender_engine = RecommenderEngine()
