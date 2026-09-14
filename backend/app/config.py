"""
Configuration settings for the Audio-Content-Based Music Discovery Recommender.
"""
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)
QDRANT_STORAGE_PATH = str(DATA_DIR / "qdrant_db")

class Settings(BaseModel):
    PROJECT_NAME: str = "Acoustic Vault - Music Discovery Engine"
    API_V1_PREFIX: str = "/api/v1"
    
    # Audio Feature Extraction Settings
    SAMPLE_RATE: int = 16000
    WINDOW_SEC: float = 30.0
    HOP_SEC: float = 10.0
    EMBEDDING_DIM: int = 64
    
    # Recommender Scoring & Anti-Popularity Weights
    DEFAULT_OBSCURITY_FACTOR: float = 0.75  # λ between 0.0 (pure acoustic) and 1.0 (extreme underground)
    MAX_VIEWS_NORMALIZER: int = 50_000_000  # Normalization denominator for log view count
    SESSION_COOLDOWN_HOURS: int = 12
    DEFAULT_BATCH_SIZE: int = 10
    
    # Vector DB Collection Name
    COLLECTION_NAME: str = "acoustic_tracks"
    
settings = Settings()
