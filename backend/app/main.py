"""
Main FastAPI Application Entrypoint.
Exposes REST and SSE endpoints for recommendations, feedback, ingestion, and catalog exploration.
"""
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Dict, Any, List
import os

from .config import settings, BASE_DIR
from .models.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    SessionFeedbackRequest,
    IngestURLRequest,
    Track,
    GalaxyResponse
)
from .services.vector_store import vector_store
from .services.recommender import recommender_engine
from .services.session_manager import session_manager
from .services.ingest_service import ingest_service
from .seed_catalog import init_seed_catalog_if_empty, reseed_amharic_catalog

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_seed_catalog_if_empty()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Zero-Replay, Audio-Content-Based Music Discovery Engine with YouTube History Isolation",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local development and embedded web players
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Core Recommendation Endpoints -----------------

@app.post(f"{settings.API_V1_PREFIX}/recommendations/next", response_model=RecommendationResponse)
async def get_next_recommendations(request: RecommendationRequest):
    """
    Generate the next batch of non-repeating acoustic discovery tracks.
    Applies the Obscurity Slider (λ), acoustic vector distance, and strict session cooldowns.
    """
    response = recommender_engine.generate_recommendations(request)
    return response

@app.post(f"{settings.API_V1_PREFIX}/sessions/feedback")
async def record_session_feedback(request: SessionFeedbackRequest):
    """
    Record track completion or early skip to update the ephemeral session cooldown state.
    """
    session = session_manager.record_feedback(
        session_token=request.session_token,
        track_id=request.track_id,
        event_type=request.event_type
    )
    return {
        "status": "success",
        "session_token": session.session_token,
        "cooldown_active_count": len(session.get_all_cooldown_ids())
    }

# ----------------- On-Demand Ingestion & SSE Progress -----------------

@app.post(f"{settings.API_V1_PREFIX}/ingest/url")
async def ingest_youtube_url(request: IngestURLRequest):
    """
    Asynchronously ingest and extract acoustic features from a YouTube URL.
    Returns a task_id for streaming real-time progress via SSE.
    """
    task_id = ingest_service.start_ingestion_task(request.youtube_url)
    return {
        "task_id": task_id,
        "status": "QUEUED",
        "stream_url": f"{settings.API_V1_PREFIX}/ingest/stream/{task_id}"
    }

@app.get(f"{settings.API_V1_PREFIX}/ingest/stream/{{task_id}}")
async def stream_ingest_progress(task_id: str):
    """
    Server-Sent Events (SSE) endpoint to monitor real-time feature extraction progress.
    """
    return StreamingResponse(
        ingest_service.subscribe_progress(task_id),
        media_type="text/event-stream"
    )

# ----------------- Catalog & Metadata -----------------

@app.post(f"{settings.API_V1_PREFIX}/catalog/check-url")
async def check_catalog_url(request: IngestURLRequest):
    """
    Fast-Path Check: Determines if a YouTube URL is already indexed in the catalog.
    If found, returns the track immediately, bypassing audio extraction.
    """
    video_id = ingest_service.extract_youtube_id(request.youtube_url)
    if not video_id:
        return {"exists": False, "youtube_video_id": None, "track": None}

    track = vector_store.get_track_by_youtube_id(video_id)
    if track:
        return {"exists": True, "youtube_video_id": video_id, "track": track}
    return {"exists": False, "youtube_video_id": video_id, "track": None}

@app.get(f"{settings.API_V1_PREFIX}/catalog/tracks")
async def list_catalog_tracks(limit: int = 50):
    """
    Retrieve indexed catalog tracks for seed exploration.
    """
    tracks = vector_store.get_all_tracks(limit=limit)
    return {
        "count": len(tracks),
        "tracks": tracks
    }

@app.get(f"{settings.API_V1_PREFIX}/catalog/galaxy", response_model=GalaxyResponse)
async def get_galaxy_map():
    """
    Retrieve all catalog tracks with their projected 2D latent space coordinates
    for the interactive Canvas Galaxy Visualizer.
    """
    points = vector_store.get_galaxy_points()
    return GalaxyResponse(count=len(points), points=points)

@app.get(f"{settings.API_V1_PREFIX}/catalog/qenet-modes")
async def get_qenet_modes():
    """
    Returns the 4 primary Ethiopian pentatonic modal scales (Qenet) with their interval formulas.
    """
    return {
        "modes": [
            {
                "id": "Tizita",
                "name_en": "Tizita",
                "name_am": "ትዝታ",
                "color_hex": "#f59e0b",
                "description": "Nostalgic, deeply reflective, and emotional ballads of memory and longing.",
                "intervals": [0, 2, 4, 7, 9],
                "submodes": ["Tizita Major", "Tizita Minor"]
            },
            {
                "id": "Bati",
                "name_en": "Bati",
                "name_am": "ባቲ",
                "color_hex": "#06b6d4",
                "description": "Mystical, contemplative, bluesy desert modal harmonies.",
                "intervals": [0, 4, 5, 7, 11],
                "submodes": ["Bati Major", "Bati Minor"]
            },
            {
                "id": "Ambassel",
                "name_en": "Ambassel",
                "name_am": "አምባሰል",
                "color_hex": "#10b981",
                "description": "Pastoral, mountainous, epic narrative and soulful acoustic storytelling.",
                "intervals": [0, 1, 5, 7, 8],
                "submodes": ["Ambassel"]
            },
            {
                "id": "Anchihoye",
                "name_en": "Anchihoye",
                "name_am": "አንቺሆዬ",
                "color_hex": "#ec4899",
                "description": "Celebratory, energetic, driving spiritual yearning and dynamic groove.",
                "intervals": [0, 1, 5, 6, 10],
                "submodes": ["Anchihoye"]
            }
        ]
    }

@app.get(f"{settings.API_V1_PREFIX}/catalog/vibe-presets")
async def get_vibe_presets():
    """
    Returns the curated discovery presets.
    """
    return {
        "presets": [
            {
                "id": "buna_tizita",
                "label": "Buna & Tizita",
                "icon": "☕",
                "description": "Late-night coffee & soulful Tizita ballads (BPM < 95, deep memory)",
                "target_qenet": "Tizita",
                "target_bpm_hint": "< 95 BPM",
                "obscurity_val": 80
            },
            {
                "id": "eskista_beat",
                "label": "Eskista Driving Beat",
                "icon": "⚡",
                "description": "Fast polyrhythms, shoulder-dance percussion, and high danceability (BPM > 118)",
                "target_qenet": None,
                "target_bpm_hint": "118+ BPM",
                "obscurity_val": 50
            },
            {
                "id": "mulatu_lounge",
                "label": "Mulatu's Lounge",
                "icon": "🎷",
                "description": "70s Golden Ethio-Jazz, vibraphone textures, and vintage horn grooves",
                "target_qenet": None,
                "target_bpm_hint": "80 - 120 BPM",
                "obscurity_val": 65
            },
            {
                "id": "azmari_underground",
                "label": "The Azmari Underground",
                "icon": "🔮",
                "description": "100% deep underground Masenqo & Krar raw traditional recordings",
                "target_qenet": None,
                "target_bpm_hint": "All Tempos",
                "obscurity_val": 100
            }
        ]
    }

@app.post(f"{settings.API_V1_PREFIX}/catalog/reset-amharic")
async def reset_catalog_to_amharic():
    """
    Resets and re-indexes the vector database exclusively with authentic Amharic music tracks.
    """
    reseed_amharic_catalog()
    return {
        "status": "success",
        "message": "Vector catalog successfully reset to 100% Amharic & Ethiopian tracks.",
        "indexed_tracks": vector_store.count_tracks()
    }

@app.get(f"{settings.API_V1_PREFIX}/tracks/{{track_id}}")
async def get_track(track_id: str):
    """
    Retrieve full acoustic profile and metadata for a given track.
    """
    track = vector_store.get_track_by_id(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return track

@app.get(f"{settings.API_V1_PREFIX}/vault/starred")
async def get_starred_vault():
    """
    Retrieve persisted starred favorite tracks from data/starred.yaml.
    """
    from backend.app.services.vault_storage import vault_storage
    starred = vault_storage.get_starred()
    return {
        "total_starred": len(starred),
        "starred_tracks": starred
    }

@app.post(f"{settings.API_V1_PREFIX}/vault/starred")
async def sync_starred_vault(payload: Dict[str, Any] = Body(...)):
    """
    Save starred favorite tracks to data/starred.yaml and data/starred.json.
    """
    from backend.app.services.vault_storage import vault_storage
    tracks = payload.get("starred_tracks", [])
    result = vault_storage.save_starred(tracks)
    return result

@app.get(f"{settings.API_V1_PREFIX}/health")
async def health_check():
    return {
        "status": "healthy",
        "indexed_tracks": vector_store.count_tracks(),
        "vector_dimensions": settings.EMBEDDING_DIM
    }

# ----------------- Static Frontend Hosting -----------------
FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")
