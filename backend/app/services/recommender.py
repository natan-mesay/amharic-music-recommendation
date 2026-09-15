"""
Core Recommendation and Anti-Popularity Discovery Engine.
Enhanced with Ethiopian Qenet Pentatonic Mode filtering, Vibe presets, and Era selection.
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

    def apply_vibe_preset_defaults(self, request: RecommendationRequest) -> Tuple[RecommendationRequest, Optional[str]]:
        """
        Applies preset acoustic constraints if a vibe_preset is active.
        """
        vibe = request.vibe_preset
        if not vibe or vibe.lower() in ["all", "none", ""]:
            return request, None

        vibe_key = vibe.lower()
        if vibe_key == "buna_tizita":
            # Chill, late night Buna & Tizita: low tempo, high obscurity
            request.qenet_filter = "Tizita"
            request.max_bpm = 95.0
            request.obscurity_factor = max(request.obscurity_factor, 0.75)
            return request, "buna_tizita"
        elif vibe_key == "eskista_beat":
            # Driving high energy dance
            request.min_bpm = 118.0
            request.obscurity_factor = 0.50
            return request, "eskista_beat"
        elif vibe_key == "mulatu_lounge":
            # Ethio-Jazz velvet lounge: mid tempo
            request.min_bpm = 80.0
            request.max_bpm = 120.0
            return request, "mulatu_lounge"
        elif vibe_key == "azmari_underground":
            # 100% deep underground traditional masenqo/krar
            request.obscurity_factor = 1.0
            return request, "azmari_underground"

        return request, vibe

    def generate_recommendations(self, request: RecommendationRequest) -> RecommendationResponse:
        session = session_manager.get_or_create_session(request.session_token)

        # Apply Vibe Preset constraints if set
        request, active_vibe = self.apply_vibe_preset_defaults(request)

        # 1. Resolve Seed Track
        active_seed = None
        query_vector = None
        seed_id = request.seed_track_id

        if seed_id:
            seed_data = vector_store.get_track_by_id(seed_id)
            if seed_data:
                active_seed = Track(
                    track_id=seed_data["track_id"],
                    youtube_video_id=seed_data["youtube_video_id"],
                    title=seed_data["title"],
                    channel_name=seed_data["channel_name"],
                    duration_seconds=seed_data["duration_seconds"],
                    view_count=seed_data["view_count"],
                    genre_tags=seed_data.get("genre_tags", []),
                    era=seed_data.get("era", "Golden 70s"),
                    galaxy_x=seed_data.get("galaxy_x", 0.0),
                    galaxy_y=seed_data.get("galaxy_y", 0.0),
                    acoustic_features=AcousticFeatures(**seed_data["acoustic_features"])
                )
                query_vector = seed_data["acoustic_features"]["embedding"]

        # If no seed, choose the first unplayed track in catalog
        if query_vector is None:
            all_tracks = vector_store.get_all_tracks(limit=50)
            available = [t for t in all_tracks if not session.is_hard_buffered(t["track_id"])]
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
                        era=full_t.get("era", "Golden 70s"),
                        galaxy_x=full_t.get("galaxy_x", 0.0),
                        galaxy_y=full_t.get("galaxy_y", 0.0),
                        acoustic_features=AcousticFeatures(**full_t["acoustic_features"])
                    )
                    query_vector = full_t["acoustic_features"]["embedding"]
                    seed_id = full_t["track_id"]

        if query_vector is None:
            return RecommendationResponse(
                session_token=request.session_token,
                items=[],
                active_seed=None,
                active_qenet_filter=request.qenet_filter,
                active_vibe_preset=active_vibe,
                total_candidates_evaluated=0,
                cooldown_count=session.get_active_cooldown_count()
            )

        # Blend query vector with user's Liked Taste Centroid if available
        taste_centroid = session.get_taste_centroid(vector_store)
        if taste_centroid is not None:
            import numpy as np
            q_arr = np.array(query_vector)
            t_arr = np.array(taste_centroid)
            blended = 0.70 * q_arr + 0.30 * t_arr
            norm = np.linalg.norm(blended)
            if norm > 0:
                query_vector = (blended / norm).tolist()

        # 2. Retrieve Filtered Candidates from Vector DB
        fetch_limit = max(60, request.batch_size * 6)
        raw_candidates = vector_store.search_similar(
            query_vector=query_vector,
            limit=fetch_limit,
            qenet_filter=request.qenet_filter,
            era_filter=request.era_filter,
            min_bpm=request.min_bpm,
            max_bpm=request.max_bpm,
            min_duration_sec=request.min_duration_sec,
            max_duration_sec=request.max_duration_sec
        )

        # 3. Apply Soft Fatigue Decay, Obscurity Weighting & Channel Diversity
        scored_items = []
        channel_counts: Dict[str, int] = {}
        lam = request.obscurity_factor
        client_excluded = set(request.excluded_track_ids)
        seen_track_ids: Set[str] = set()
        seen_video_ids: Set[str] = set()

        if active_seed:
            seen_track_ids.add(active_seed.track_id)
            seen_video_ids.add(active_seed.youtube_video_id)

        for cand in raw_candidates:
            cid = cand["track_id"]
            vid = cand["youtube_video_id"]
            
            # Strict deduplication: skip if already seen or in active seed
            if cid in seen_track_ids or vid in seen_video_ids:
                continue
            
            # Skip if disliked or hard-buffered in active session (dual-key check)
            if session.is_hard_buffered(cid, vid) or cid in client_excluded or vid in client_excluded:
                continue

            # Prevent too many consecutive tracks from the same artist
            ch_name = cand["channel_name"]
            if channel_counts.get(ch_name, 0) >= 2:
                continue

            sim_score = float(cand.get("similarity_score", 0.0))
            norm_sim = max(0.0, min(1.0, (sim_score + 1.0) / 2.0 if sim_score < 0 else sim_score))
            obscurity_score = self.calculate_obscurity_score(cand["view_count"])

            # Base Discovery Score
            base_score = (1.0 - lam) * norm_sim + lam * obscurity_score
            
            # Multi-Tiered Discovery Scoring:
            is_all_time_heard = session.is_all_time_heard(cid, vid)
            is_liked = (cid in session.liked_track_ids) or (vid in session.liked_video_ids)

            if not is_all_time_heard and not is_liked:
                discovery_bonus = 0.25  # ✨ Tier 1: True Cold Discovery (Never heard anywhere)
            elif is_all_time_heard and not is_liked:
                discovery_bonus = -0.20 # ⏳ Tier 2: Re-Discovery (Heard in past sessions, lower priority)
            else:
                discovery_bonus = -0.35 # 🚫 Tier 3: Already in Vault (Deprioritize in discovery radio)
            
            # Soft Fatigue Penalty: allows tracks to naturally re-surface after K tracks
            fatigue_penalty = session.get_fatigue_penalty(cid, vid)
            composite = max(0.0, base_score + discovery_bonus - fatigue_penalty)

            item = RecommendationItem(
                track_id=cid,
                youtube_video_id=vid,
                title=cand["title"],
                channel_name=cand["channel_name"],
                duration_seconds=cand["duration_seconds"],
                view_count=cand["view_count"],
                genre_tags=cand.get("genre_tags", []),
                era=cand.get("era", "Golden 70s"),
                bpm=cand["bpm"],
                energy=cand["energy"],
                brightness=cand["brightness"],
                qenet_mode=cand.get("qenet_mode", "Tizita"),
                qenet_submode=cand.get("qenet_submode", "Tizita Minor"),
                galaxy_x=cand.get("galaxy_x", 0.0),
                galaxy_y=cand.get("galaxy_y", 0.0),
                acoustic_similarity_score=round(norm_sim, 4),
                obscurity_score=round(obscurity_score, 4),
                composite_score=round(composite, 4)
            )
            scored_items.append((composite, item, ch_name))

        # Sort descending by composite discovery score
        scored_items.sort(key=lambda x: x[0], reverse=True)

        final_items = []
        for comp, itm, ch in scored_items:
            if itm.track_id in seen_track_ids or itm.youtube_video_id in seen_video_ids:
                continue
            if len(final_items) >= request.batch_size:
                break
            final_items.append(itm)
            seen_track_ids.add(itm.track_id)
            seen_video_ids.add(itm.youtube_video_id)
            channel_counts[ch] = channel_counts.get(ch, 0) + 1

        # 4. Fallback Stage: If queue is under-filled due to strict filters or small catalog,
        # relax filters to guarantee the listener always receives a rich, un-empty queue.
        if len(final_items) < request.batch_size:
            broad_candidates = vector_store.search_similar(
                query_vector=query_vector,
                limit=fetch_limit
            )
            for cand in broad_candidates:
                cid = cand["track_id"]
                vid = cand["youtube_video_id"]
                if cid in seen_track_ids or vid in seen_video_ids:
                    continue
                if session.is_hard_buffered(cid, vid) or cid in client_excluded or vid in client_excluded:
                    continue

                sim_score = float(cand.get("similarity_score", 0.0))
                norm_sim = max(0.0, min(1.0, (sim_score + 1.0) / 2.0 if sim_score < 0 else sim_score))
                obscurity_score = self.calculate_obscurity_score(cand["view_count"])
                base_score = (1.0 - lam) * norm_sim + lam * obscurity_score
                
                is_all_time_heard = session.is_all_time_heard(cid, vid)
                is_liked = (cid in session.liked_track_ids) or (vid in session.liked_video_ids)

                if not is_all_time_heard and not is_liked:
                    discovery_bonus = 0.25
                elif is_all_time_heard and not is_liked:
                    discovery_bonus = -0.20
                else:
                    discovery_bonus = -0.35

                fatigue_penalty = session.get_fatigue_penalty(cid, vid)
                composite = max(0.0, base_score + discovery_bonus - fatigue_penalty)

                item = RecommendationItem(
                    track_id=cid,
                    youtube_video_id=vid,
                    title=cand["title"],
                    channel_name=cand["channel_name"],
                    duration_seconds=cand["duration_seconds"],
                    view_count=cand["view_count"],
                    genre_tags=cand.get("genre_tags", []),
                    era=cand.get("era", "Golden 70s"),
                    bpm=cand["bpm"],
                    energy=cand["energy"],
                    brightness=cand["brightness"],
                    qenet_mode=cand.get("qenet_mode", "Tizita"),
                    qenet_submode=cand.get("qenet_submode", "Tizita Minor"),
                    galaxy_x=cand.get("galaxy_x", 0.0),
                    galaxy_y=cand.get("galaxy_y", 0.0),
                    acoustic_similarity_score=round(norm_sim, 4),
                    obscurity_score=round(obscurity_score, 4),
                    composite_score=round(composite, 4)
                )
                final_items.append(item)
                seen_track_ids.add(cid)
                seen_video_ids.add(vid)
                if len(final_items) >= request.batch_size:
                    break

        # 5. Stage 4 Emergency Fallback: If still underfilled, surface least-recently-played tracks (unheard first)
        if len(final_items) < request.batch_size:
            all_catalog = vector_store.get_all_tracks(limit=100)
            def get_recency_rank(c):
                tid = c.get("track_id")
                vid = c.get("youtube_video_id")
                is_all_time = 1 if session.is_all_time_heard(tid, vid) else 0
                is_liked = 1 if (tid in session.liked_track_ids or vid in session.liked_video_ids) else 0
                last_idx = session.history[tid].last_index if tid in session.history else -1
                return (is_all_time, is_liked, last_idx)

            sorted_emergency = sorted(
                [c for c in all_catalog if not session.is_hard_buffered(c.get("track_id"), c.get("youtube_video_id")) and c.get("track_id") not in seen_track_ids and c.get("youtube_video_id") not in seen_video_ids],
                key=get_recency_rank
            )
            for cand in sorted_emergency:
                cid = cand["track_id"]
                vid = cand["youtube_video_id"]
                obscurity_score = self.calculate_obscurity_score(cand.get("view_count", 0))
                item = RecommendationItem(
                    track_id=cid,
                    youtube_video_id=vid,
                    title=cand["title"],
                    channel_name=cand["channel_name"],
                    duration_seconds=cand.get("duration_seconds", 240),
                    view_count=cand.get("view_count", 0),
                    genre_tags=cand.get("genre_tags", []),
                    era=cand.get("era", "Golden 70s"),
                    bpm=cand.get("bpm", 100.0),
                    energy=cand.get("energy", 0.5),
                    brightness=cand.get("brightness", 0.5),
                    qenet_mode=cand.get("qenet_mode", "Tizita"),
                    qenet_submode=cand.get("qenet_submode", "Tizita Minor"),
                    galaxy_x=cand.get("galaxy_x", 0.0),
                    galaxy_y=cand.get("galaxy_y", 0.0),
                    acoustic_similarity_score=0.75,
                    obscurity_score=round(obscurity_score, 4),
                    composite_score=0.60
                )
                final_items.append(item)
                seen_track_ids.add(cid)
                seen_video_ids.add(vid)
                if len(final_items) >= request.batch_size:
                    break


        return RecommendationResponse(
            session_token=request.session_token,
            items=final_items,
            active_seed=active_seed,
            active_qenet_filter=request.qenet_filter,
            active_vibe_preset=active_vibe,
            total_candidates_evaluated=len(raw_candidates),
            cooldown_count=session.get_active_cooldown_count()
        )

recommender_engine = RecommenderEngine()
