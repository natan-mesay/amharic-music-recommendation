"""
Pydantic Schemas for Requests, Responses, and Data Entities.
Enhanced with Ethiopian Qenet pentatonic intelligence and 2D Latent Galaxy coordinates.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid

class AcousticFeatures(BaseModel):
    bpm: float = Field(..., description="Estimated tempo in beats per minute")
    energy: float = Field(..., description="Normalized RMS energy (0.0 - 1.0)")
    danceability: float = Field(..., description="Rhythmic regularity score (0.0 - 1.0)")
    brightness: float = Field(..., description="Normalized spectral centroid / timbre brightness (0.0 - 1.0)")
    tonal_energy: float = Field(..., description="Harmonic tonality stability (0.0 - 1.0)")
    harmonic_key: str = Field("C", description="Estimated musical key")
    qenet_mode: str = Field("Tizita", description="Ethiopian pentatonic scale: Tizita, Bati, Ambassel, Anchihoye")
    qenet_submode: str = Field("Tizita Minor", description="Modal sub-type: e.g. Tizita Major, Tizita Minor, Bati Major")
    qenet_confidence: float = Field(0.85, description="Pentatonic template matching confidence score (0.0 - 1.0)")
    embedding: List[float] = Field(..., description="Normalized dense acoustic vector (64-dim)")

class Track(BaseModel):
    track_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    youtube_video_id: str
    title: str
    channel_name: str
    duration_seconds: int
    view_count: int
    genre_tags: List[str] = Field(default_factory=list)
    era: str = Field("Golden 70s", description="Musical era: Golden 70s, 80s-90s Cassette, Modern 2020s")
    galaxy_x: float = Field(0.0, description="Projected 2D latent space X coordinate [-1.0, 1.0]")
    galaxy_y: float = Field(0.0, description="Projected 2D latent space Y coordinate [-1.0, 1.0]")
    acoustic_features: AcousticFeatures

class RecommendationItem(BaseModel):
    track_id: str
    youtube_video_id: str
    title: str
    channel_name: str
    duration_seconds: int
    view_count: int
    genre_tags: List[str] = Field(default_factory=list)
    era: str = "Golden 70s"
    bpm: float
    energy: float
    brightness: float
    qenet_mode: str = "Tizita"
    qenet_submode: str = "Tizita Minor"
    galaxy_x: float = 0.0
    galaxy_y: float = 0.0
    acoustic_similarity_score: float
    obscurity_score: float
    composite_score: float

class RecommendationRequest(BaseModel):
    seed_track_id: Optional[str] = Field(None, description="Anchor track ID for acoustic similarity")
    session_token: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Ephemeral session token")
    obscurity_factor: float = Field(0.75, ge=0.0, le=1.0, description="λ slider: 0 = acoustic only, 1 = deep underground")
    qenet_filter: Optional[str] = Field(None, description="Optional Qenet scale filter: All, Tizita, Bati, Ambassel, Anchihoye")
    vibe_preset: Optional[str] = Field(None, description="Optional discovery preset: buna_tizita, eskista_beat, mulatu_lounge, azmari_underground")
    era_filter: Optional[str] = Field(None, description="Optional era filter: Golden 70s, 80s-90s Cassette, Modern 2020s")
    min_bpm: Optional[float] = Field(None, description="Optional minimum tempo filter")
    max_bpm: Optional[float] = Field(None, description="Optional maximum tempo filter")
    min_duration_sec: Optional[int] = Field(None, description="Minimum duration filter in seconds")
    max_duration_sec: Optional[int] = Field(None, description="Maximum duration filter in seconds")
    batch_size: int = Field(10, ge=1, le=50)
    excluded_track_ids: List[str] = Field(default_factory=list, description="Client-side excluded track IDs")

class RecommendationResponse(BaseModel):
    session_token: str
    items: List[RecommendationItem]
    active_seed: Optional[Track] = None
    active_qenet_filter: Optional[str] = None
    active_vibe_preset: Optional[str] = None
    total_candidates_evaluated: int
    cooldown_count: int

class SessionFeedbackRequest(BaseModel):
    session_token: str
    track_id: str
    event_type: str = Field(..., description="COMPLETED, SKIPPED, DISLIKED, BOOKMARKED")
    listen_duration_seconds: Optional[float] = 0.0

class IngestURLRequest(BaseModel):
    youtube_url: str

class IngestTaskStatus(BaseModel):
    task_id: str
    status: str  # QUEUED, PROCESSING, COMPLETED, FAILED
    stage: str
    pct: int
    track: Optional[Track] = None
    error_message: Optional[str] = None

class GalaxyTrackPoint(BaseModel):
    track_id: str
    youtube_video_id: str
    title: str
    channel_name: str
    duration_seconds: int
    view_count: int
    era: str
    qenet_mode: str
    qenet_submode: str
    bpm: float
    energy: float
    brightness: float
    galaxy_x: float
    galaxy_y: float

class GalaxyResponse(BaseModel):
    count: int
    points: List[GalaxyTrackPoint]

class QenetModeInfo(BaseModel):
    id: str
    name_en: str
    name_am: str
    intervals: List[int]
    description: str
    color_hex: str
    submodes: List[str]

class VibePresetInfo(BaseModel):
    id: str
    label: str
    icon: str
    description: str
    target_qenet: Optional[str] = None
    target_bpm_hint: str
    obscurity_val: int
