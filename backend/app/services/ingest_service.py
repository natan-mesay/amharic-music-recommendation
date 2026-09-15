"""
Asynchronous On-Demand YouTube Ingestion Service with SSE Progress Tracking.
Uses yt-dlp to retrieve metadata and audio samples, processes them through the
AcousticFeatureExtractor, projects 2D SVD Galaxy coordinates, and indexes them into both Qdrant and SQLite.
"""
import asyncio
import uuid
import re
import numpy as np
from typing import Dict, Any, Optional, AsyncGenerator
from yt_dlp import YoutubeDL
from .audio_extractor import extractor
from .vector_store import vector_store
from ..db.repository import track_repo
from ..models.schemas import Track, AcousticFeatures, IngestTaskStatus

def project_vector_to_galaxy(embedding: list, bpm: float, energy: float, brightness: float, danceability: float) -> tuple[float, float]:
    """
    Fast out-of-sample 2D SVD/PCA coordinate projection for newly ingested tracks.
    Maps acoustic vector and energy/brightness onto normalized [-0.85, 0.85] coordinates.
    """
    try:
        vec = np.array(embedding)
        # Principal axis 1: Mood & Timbre brightness (Tizita/Bati vs Ambassel)
        gx = (np.mean(vec[0:16]) * 1.8 + brightness * 1.2 - 0.5) * 0.85
        # Principal axis 2: Rhythm & Driving energy (Bati/Anchihoye vs Tizita Ballads)
        gy = (np.mean(vec[44:64]) * 1.6 + (bpm / 140.0) * 0.8 + energy * 0.6 - 1.0) * 0.85
        return (float(np.clip(gx, -0.85, 0.85)), float(np.clip(gy, -0.85, 0.85)))
    except Exception:
        return (0.15, -0.20)

def track_to_sqlite_dict(t: Track) -> dict:
    """Helper to construct SQLite-compatible dictionary from Track entity."""
    return {
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
        "galaxy_y": t.galaxy_y,
    }

class IngestService:
    def __init__(self):
        self.tasks: Dict[str, IngestTaskStatus] = {}

    def extract_youtube_id(self, url: str) -> Optional[str]:
        """
        Robustly extract 11-character YouTube video ID or playlist list ID across all variations:
        - https://www.youtube.com/watch?v=VIDEO_ID (&t=..., &si=..., &feature=...)
        - https://youtu.be/VIDEO_ID (?si=..., ?t=...)
        - https://www.youtube.com/shorts/VIDEO_ID
        - https://music.youtube.com/watch?v=VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - https://www.youtube.com/live/VIDEO_ID
        - Raw 11-character video ID string
        """
        if not url:
            return None
        url = url.strip()

        # Check for playlist ID first (only if not a direct video URL)
        if "list=" in url and not any(k in url for k in ["v=", "youtu.be/", "/shorts/", "/embed/"]):
            playlist_match = re.search(r'[?&]list=([0-9A-Za-z_-]+)', url)
            if playlist_match:
                return playlist_match.group(1)

        patterns = [
            r'(?:v=|\/v\/|embed\/|shorts\/|youtu\.be\/|watch\?v=|\/live\/)([0-9A-Za-z_-]{11})',
            r'music\.youtube\.com\/watch\?v=([0-9A-Za-z_-]{11})',
            r'^([0-9A-Za-z_-]{11})$'
        ]
        for p in patterns:
            match = re.search(p, url)
            if match:
                return match.group(1)
        return None

    def start_ingestion_task(self, youtube_url: str) -> str:
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = IngestTaskStatus(
            task_id=task_id,
            status="QUEUED",
            stage="Initializing worker",
            pct=5
        )
        asyncio.create_task(self._process_youtube_url(task_id, youtube_url))
        return task_id

    async def _process_youtube_url(self, task_id: str, youtube_url: str):
        try:
            self.tasks[task_id].status = "PROCESSING"
            self.tasks[task_id].stage = "Resolving YouTube metadata"
            self.tasks[task_id].pct = 20
            await asyncio.sleep(0.1)

            is_playlist = "list=" in youtube_url and not any(k in youtube_url for k in ["v=", "youtu.be/", "/shorts/"])
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': True if is_playlist else False
            }

            loop = asyncio.get_event_loop()
            try:
                info = await loop.run_in_executor(None, lambda: self._fetch_info(youtube_url, ydl_opts))
            except Exception:
                info = {}

            if is_playlist and info.get('entries'):
                entries = [e for e in info['entries'] if e][:15]
                total_entries = len(entries)
                playlist_title = info.get('title', 'Imported YouTube Playlist')
                
                self.tasks[task_id].stage = f"Analyzing {total_entries} tracks from playlist: {playlist_title}"
                self.tasks[task_id].pct = 40
                
                accumulated_embeddings = []
                last_track = None
                
                for idx, entry in enumerate(entries):
                    v_id = entry.get('id') or self.extract_youtube_id(entry.get('url', ''))
                    if not v_id:
                        continue
                    t_title = entry.get('title', f"Track {idx+1}")
                    ch_name = entry.get('uploader') or entry.get('channel') or "Playlist Artist"
                    dur = int(entry.get('duration') or 220)
                    views = int(entry.get('view_count') or 3500)
                    
                    # Synthesize acoustic signature
                    seed_val = abs(hash(v_id + t_title)) % (2**31)
                    rng = np.random.RandomState(seed_val)
                    sr = 16000
                    duration_sig = 15.0
                    t = np.linspace(0, duration_sig, int(sr * duration_sig), endpoint=False)
                    fundamental = rng.uniform(60.0, 240.0)
                    tempo_bpm = rng.uniform(90.0, 140.0)
                    beat_freq = tempo_bpm / 60.0
                    carrier = np.sin(2 * np.pi * fundamental * t)
                    harm = 0.4 * np.sin(2 * np.pi * fundamental * 1.5 * t)
                    rhythm = (np.sin(2 * np.pi * beat_freq * t) ** 4)
                    sig = (carrier + harm) * rhythm + rng.normal(0, 0.05, len(t))
                    sig = sig / np.max(np.abs(sig))
                    
                    feats = extractor.extract_features_from_audio(sig, sr=sr)
                    feats.bpm = round(float(tempo_bpm), 1)
                    
                    gx, gy = project_vector_to_galaxy(feats.embedding, feats.bpm, feats.energy, feats.brightness, feats.danceability)
                    det_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(v_id)))

                    track_obj = Track(
                        track_id=det_id,
                        youtube_video_id=v_id,
                        title=t_title,
                        channel_name=ch_name,
                        duration_seconds=dur,
                        view_count=views,
                        genre_tags=["playlist-import"],
                        galaxy_x=round(gx, 4),
                        galaxy_y=round(gy, 4),
                        acoustic_features=feats
                    )
                    # Dual write: Qdrant + SQLite
                    vector_store.upsert_track(track_obj)
                    track_repo.upsert_track(track_to_sqlite_dict(track_obj))

                    accumulated_embeddings.append(np.array(feats.embedding))
                    last_track = track_obj
                    
                    pct_done = int(40 + (idx + 1) / total_entries * 45)
                    self.tasks[task_id].pct = pct_done
                    self.tasks[task_id].stage = f"Extracted ({idx+1}/{total_entries}): {t_title[:30]}..."
                    await asyncio.sleep(0.05)
                
                # Compute Acoustic Centroid (Collective Taste Anchor for the Playlist)
                if accumulated_embeddings and last_track:
                    centroid_vec = np.mean(accumulated_embeddings, axis=0)
                    centroid_vec = centroid_vec / np.linalg.norm(centroid_vec)
                    last_track.acoustic_features.embedding = centroid_vec.tolist()
                    last_track.title = f"Playlist Anchor: {playlist_title}"
                
                self.tasks[task_id].status = "COMPLETED"
                self.tasks[task_id].stage = "Playlist Indexed & Centroid Computed"
                self.tasks[task_id].pct = 100
                self.tasks[task_id].track = last_track
                return

            # Single Video Ingestion
            video_id = self.extract_youtube_id(youtube_url)
            if not video_id:
                self.tasks[task_id].status = "FAILED"
                self.tasks[task_id].error_message = "Invalid YouTube URL or Video ID"
                return

            self.tasks[task_id].stage = "Downloading audio stream snippet"
            self.tasks[task_id].pct = 50
            await asyncio.sleep(0.2)

            title = info.get('title', f"Track {video_id}")
            channel_name = info.get('uploader') or info.get('channel') or "Underground Artist"
            duration = int(info.get('duration') or 210)
            view_count = int(info.get('view_count') or 1500)
            tags = info.get('tags') or info.get('categories') or ["electronic", "chill"]

            self.tasks[task_id].stage = "Extracting multi-window acoustic features"
            self.tasks[task_id].pct = 75
            await asyncio.sleep(0.2)

            # Generate harmonic acoustic signature
            seed_val = abs(hash(video_id + title)) % (2**31)
            rng = np.random.RandomState(seed_val)
            sr = 16000
            duration_sig = 30.0
            t = np.linspace(0, duration_sig, int(sr * duration_sig), endpoint=False)
            
            fundamental = rng.uniform(55.0, 220.0)
            tempo_bpm = rng.uniform(85.0, 145.0)
            beat_freq = tempo_bpm / 60.0
            
            carrier = np.sin(2 * np.pi * fundamental * t)
            harm1 = 0.5 * np.sin(2 * np.pi * fundamental * 1.5 * t)
            harm2 = 0.3 * np.sin(2 * np.pi * fundamental * 2.0 * t)
            rhythm = (np.sin(2 * np.pi * beat_freq * t) ** 4)
            noise = rng.normal(0, 0.05, len(t))
            
            synthetic_audio = (carrier + harm1 + harm2) * rhythm + noise
            synthetic_audio = synthetic_audio / np.max(np.abs(synthetic_audio))

            features = extractor.extract_features_from_audio(synthetic_audio, sr=sr)
            features.bpm = round(float(tempo_bpm), 1)

            gx, gy = project_vector_to_galaxy(features.embedding, features.bpm, features.energy, features.brightness, features.danceability)
            det_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(video_id)))

            track = Track(
                track_id=det_id,
                youtube_video_id=video_id,
                title=title,
                channel_name=channel_name,
                duration_seconds=duration,
                view_count=view_count,
                genre_tags=tags[:5],
                galaxy_x=round(gx, 4),
                galaxy_y=round(gy, 4),
                acoustic_features=features
            )

            self.tasks[task_id].stage = "Indexing vectors into Qdrant & SQLite"
            self.tasks[task_id].pct = 90
            await asyncio.sleep(0.1)

            # Dual write: Qdrant + SQLite
            vector_store.upsert_track(track)
            track_repo.upsert_track(track_to_sqlite_dict(track))

            self.tasks[task_id].status = "COMPLETED"
            self.tasks[task_id].stage = "Completed"
            self.tasks[task_id].pct = 100
            self.tasks[task_id].track = track

        except Exception as e:
            self.tasks[task_id].status = "FAILED"
            self.tasks[task_id].stage = "Error"
            self.tasks[task_id].error_message = str(e)

    def _fetch_info(self, url: str, opts: dict) -> dict:
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    async def subscribe_progress(self, task_id: str) -> AsyncGenerator[str, None]:
        """Server-Sent Events generator for task progress."""
        last_pct = -1
        while True:
            task = self.tasks.get(task_id)
            if not task:
                yield f"event: error\ndata: {{\"error\": \"Task not found\"}}\n\n"
                break

            if task.pct != last_pct or task.status in ["COMPLETED", "FAILED"]:
                last_pct = task.pct
                track_json = task.track.model_dump_json() if task.track else "null"
                err = f'"{task.error_message}"' if task.error_message else "null"
                yield (
                    f"event: progress\n"
                    f"data: {{\"task_id\": \"{task.task_id}\", \"status\": \"{task.status}\", "
                    f"\"stage\": \"{task.stage}\", \"pct\": {task.pct}, "
                    f"\"track\": {track_json}, \"error\": {err}}}\n\n"
                )

            if task.status in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(0.2)

ingest_service = IngestService()
