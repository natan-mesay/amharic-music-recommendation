# Acoustic Vault: Audio-Content-Based Music Discovery Recommender

A zero-login, privacy-preserving music discovery engine engineered to overcome algorithmic popularity bubbles and replay loops. Powered by multi-window acoustic vector embeddings, dynamic obscurity weighting, and a sandboxed `youtube-nocookie.com` client.

---

## 🌟 Key Features

1. **Zero-Replay Discovery Engine**:
   - Implements a stateful session cooldown ledger that strictly blocks previously played and skipped songs from repeating.
2. **Audio-Content-Driven (Cold-Start Proof)**:
   - Evaluates tracks purely on raw acoustic features (timbral brightness, BPM tempo, chroma tonality, harmonic energy, and spectral contrast) extracted via 30-second sliding windows.
3. **Dynamic Obscurity Dial ($\lambda$)**:
   - Control your exploration depth from 0% (*Acoustic Match*) to 100% (*Deep Underground Abyss*), actively boosting underground tracks with small listener counts.
4. **YouTube History Isolation & Continuous Autoplay**:
   - Interactive YouTube IFrame Player API integration on `youtube-nocookie.com` with a 5-second **"Up Next" countdown overlay**, persistent **Autoplay toggle**, and infinite dynamic re-seeding without polluting your personal YouTube history.
5. **Instant URL Fast-Path & SSE Ingestion**:
   - Paste any YouTube link to instantly verify catalog cache hits or extract acoustic descriptors in real-time, immediately starting continuous playback and recommendation generation.
6. **Standard Keyboard Navigation**:
   - `Shift + N` (Next track), `Shift + P` (Previous track), `Space` / `K` (Play/Pause), `M` (Mute/Unmute).

---

## 📐 Algorithmic Scoring Formula

For any candidate track $t$ given a seed track $s$:

$$\text{CompositeScore}(t) = (1 - \lambda) \cdot \mathcal{S}_{\text{acoustic}}(s, t) + \lambda \cdot \mathcal{O}(t) - \mathcal{P}_{\text{cooldown}}(t)$$

Where:
* $\mathcal{S}_{\text{acoustic}}(s, t) = \cos(\vec{V}_s, \vec{V}_t)$: Cosine similarity between 64-dimensional acoustic vectors.
* $\mathcal{O}(t) = \max\left(0, 1 - \frac{\log_{10}(\text{views}(t) + 1)}{\log_{10}(\text{MaxViews} + 1)}\right)$: **The Obscurity Index** ($1.0$ for underground tracks, $0.0$ for viral hits).
* $\lambda \in [0.0, 1.0]$: User-controlled **Obscurity Slider**.
* $\mathcal{P}_{\text{cooldown}}(t) = \infty$ if $t \in \text{SessionCooldown}$, guaranteeing non-repeating queues.

---

## 🚀 Quick Start

### 1. Run the Server
```bash
./start.sh
```
Or manually:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Open the Web Application
Navigate to `http://localhost:8000` in your web browser.

### 3. Run Automated Tests
```bash
PYTHONPATH=. pytest backend/tests/test_recommender.py -v
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/recommendations/next` | Fetches next non-repeating acoustic discovery queue. |
| `POST` | `/api/v1/sessions/feedback` | Logs play/skip events to update session cooldown state. |
| `POST` | `/api/v1/catalog/check-url` | Fast-path lookup to check if a YouTube URL is already indexed. |
| `POST` | `/api/v1/ingest/url` | Queues on-demand YouTube audio analysis. |
| `GET` | `/api/v1/ingest/stream/{task_id}` | Server-Sent Events stream for real-time extraction progress. |
| `GET` | `/api/v1/catalog/tracks` | Returns indexed catalog tracks. |
| `GET` | `/api/v1/health` | Health and vector index count status. |

---

## 📂 Project Structure

```
recommender/
├── backend/
│   ├── app/
│   │   ├── config.py                  # System thresholds and paths
│   │   ├── main.py                    # FastAPI entrypoint, routes, SSE
│   │   ├── seed_catalog.py            # Pre-seeded diverse underground catalog
│   │   ├── models/
│   │   │   └── schemas.py             # Pydantic data schemas
│   │   └── services/
│   │       ├── audio_extractor.py     # 30s windowed DSP acoustic embedder (64-dim)
│   │       ├── vector_store.py        # Qdrant vector database (Cosine HNSW)
│   │       ├── recommender.py         # Anti-popularity & zero-replay ranking
│   │       ├── session_manager.py     # Ephemeral session cooldown state
│   │       └── ingest_service.py      # Async yt-dlp worker with SSE progress
│   └── tests/
│       └── test_recommender.py        # Automated test suite
├── frontend/                          # Clean dark-mode UI with sandboxed player
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── start.sh                           # Bootstrap launcher
├── requirements.txt
└── README.md
```
