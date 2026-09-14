"""
Main FastAPI Application Entrypoint.
Exposes REST and SSE endpoints for recommendations, feedback, ingestion, and catalog exploration.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from .config import settings, BASE_DIR
from .models.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    SessionFeedbackRequest,
    IngestURLRequest,
    Track
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
