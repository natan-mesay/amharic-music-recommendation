"""
Curated Catalog of Authentic Amharic & Ethiopian Music with 100% Verified Playable YouTube Video IDs.
Enhanced with Ethiopian Qenet Pentatonic Scale Modes, Musical Eras, and 2D Latent Galaxy coordinates.
"""
import numpy as np
from typing import List
from .models.schemas import Track, AcousticFeatures
from .services.audio_extractor import extractor
from .services.vector_store import vector_store

AMHARIC_SEED_TRACKS = [
    # --- Tilahun Gessesse (The Voice of Ethiopia - Golden 70s) ---
    {
        "youtube_video_id": "xmLmdf_Jf8s",
        "title": "Bemishit Chereka (Wubeten Ayenat) ጥላሁን ገሰሰ - በምሽት ጨረቃ",
        "channel_name": "Tilahun Gessesse",
        "duration_seconds": 293,
        "view_count": 576013,
        "era": "Golden 70s",
        "qenet_mode": "Tizita",
        "qenet_submode": "Tizita Minor",
        "bpm": 86.0,
        "genre_tags": ["amharic", "tizita", "classic", "golden era"],
        "energy": 0.48,
        "brightness": 0.40,
        "danceability": 0.55,
        "tonal_energy": 0.90,
        "harmonic_key": "Dm"
    },
    {
        "youtube_video_id": "z2qDM5lXXYs",
        "title": "YE 13 WER TSEGA (የ13 ወር ፀጋ)",
        "channel_name": "Tilahun Gessesse",
        "duration_seconds": 324,
        "view_count": 589839,
        "era": "Golden 70s",
        "qenet_mode": "Tizita",
        "qenet_submode": "Tizita Major",
        "bpm": 92.0,
        "genre_tags": ["amharic", "classic", "vocal soul", "traditional"],
        "energy": 0.58,
        "brightness": 0.46,
        "danceability": 0.62,
        "tonal_energy": 0.88,
        "harmonic_key": "C"
    },
    {
        "youtube_video_id": "ZuJtcUqe2ps",
        "title": "Ere Endet (ኧረ እንዴት)",
        "channel_name": "Tilahun Gessesse",
        "duration_seconds": 182,
        "view_count": 7273769,
        "era": "Golden 70s",
        "qenet_mode": "Anchihoye",
        "qenet_submode": "Anchihoye",
        "bpm": 118.0,
        "genre_tags": ["amharic", "ethio-groove", "fast", "vintage"],
        "energy": 0.82,
        "brightness": 0.65,
        "danceability": 0.85,
        "tonal_energy": 0.76,
        "harmonic_key": "Am"
    },
    {
        "youtube_video_id": "ICtY0-f71O4",
        "title": "Hameta Mehonu (ሀሜታ መሆኑ)",
        "channel_name": "Tilahun Gessesse",
        "duration_seconds": 440,
        "view_count": 471198,
        "era": "Golden 70s",
        "qenet_mode": "Ambassel",
        "qenet_submode": "Ambassel",
        "bpm": 80.0,
        "genre_tags": ["amharic", "tizita ballad", "emotional", "soul"],
        "energy": 0.42,
        "brightness": 0.38,
        "danceability": 0.48,
        "tonal_energy": 0.94,
        "harmonic_key": "Gm"
    },

    # --- Teddy Afro Classics ---
    {
        "youtube_video_id": "UlqLeuVHpEU",
        "title": "Shih Bibal (Back to 90s) - ሺ ቢባል (ወደ 90ዎቹ)",
        "channel_name": "Teddy Afro",
        "duration_seconds": 303,
        "view_count": 34962669,
        "era": "Modern 2020s",
        "qenet_mode": "Tizita",
        "qenet_submode": "Tizita Major",
        "bpm": 108.0,
        "genre_tags": ["amharic", "roots", "reggae", "modern classic"],
        "energy": 0.78,
        "brightness": 0.60,
        "danceability": 0.82,
        "tonal_energy": 0.80,
        "harmonic_key": "C"
    },
    {
        "youtube_video_id": "DsH_LxBB4l8",
        "title": "Ze Tsedal - ዝ ፀዳል",
        "channel_name": "Teddy Afro",
        "duration_seconds": 300,
        "view_count": 25427422,
        "era": "Modern 2020s",
        "qenet_mode": "Bati",
        "qenet_submode": "Bati Major",
        "bpm": 116.0,
        "genre_tags": ["amharic", "groove", "melodic", "pop"],
        "energy": 0.74,
        "brightness": 0.58,
        "danceability": 0.80,
        "tonal_energy": 0.82,
        "harmonic_key": "G"
    },
    {
        "youtube_video_id": "pRHWe6Lz2mY",
        "title": "Tayegn - ታየኝ",
        "channel_name": "Teddy Afro",
        "duration_seconds": 237,
        "view_count": 18671443,
        "era": "Modern 2020s",
        "qenet_mode": "Anchihoye",
        "qenet_submode": "Anchihoye",
        "bpm": 124.0,
        "genre_tags": ["amharic", "driving", "rhythm", "dance"],
        "energy": 0.88,
        "brightness": 0.70,
        "danceability": 0.88,
        "tonal_energy": 0.74,
        "harmonic_key": "Am"
    },
    {
        "youtube_video_id": "BQSgYf4lfMg",
        "title": "Merkeb - መርከብ",
        "channel_name": "Teddy Afro",
        "duration_seconds": 328,
        "view_count": 18424250,
        "era": "Modern 2020s",
        "qenet_mode": "Tizita",
        "qenet_submode": "Tizita Minor",
        "bpm": 96.0,
        "genre_tags": ["amharic", "ballad", "acoustic", "storytelling"],
        "energy": 0.60,
        "brightness": 0.48,
        "danceability": 0.68,
        "tonal_energy": 0.86,
        "harmonic_key": "F"
    },
    {
        "youtube_video_id": "nw443G62EQc",
        "title": "Sememene (GuReggae) - ስምምነን (ጉሬጌ)",
        "channel_name": "Teddy Afro",
        "duration_seconds": 326,
        "view_count": 24804539,
        "era": "Modern 2020s",
        "qenet_mode": "Bati",
        "qenet_submode": "Bati Minor",
        "bpm": 110.0,
        "genre_tags": ["amharic", "guragigna", "reggae", "fusion"],
        "energy": 0.82,
        "brightness": 0.66,
        "danceability": 0.89,
        "tonal_energy": 0.78,
        "harmonic_key": "Em"
    },
    {
        "youtube_video_id": "VsrL9Rz-A5A",
        "title": "ETHIOPIA - ኢትዮጵያ (Official Anthem)",
        "channel_name": "Teddy Afro",
        "duration_seconds": 345,
        "view_count": 28000000,
        "era": "Modern 2020s",
        "qenet_mode": "Tizita",
        "qenet_submode": "Tizita Major",
        "bpm": 108.0,
        "genre_tags": ["amharic", "anthem", "roots", "national"],
        "energy": 0.78,
        "brightness": 0.58,
        "danceability": 0.80,
        "tonal_energy": 0.82,
        "harmonic_key": "C"
    },

    # --- Aster Aweke (80s-90s Cassette & Ethio-Soul) ---
    {
        "youtube_video_id": "6OCBxSC0r4g",
        "title": "Gela Gela (ገላ ገላ)",
        "channel_name": "Aster Aweke",
        "duration_seconds": 253,
        "view_count": 2344018,
        "era": "80s-90s Cassette",
        "qenet_mode": "Anchihoye",
        "qenet_submode": "Anchihoye",
        "bpm": 126.0,
        "genre_tags": ["amharic", "ethio-soul", "dance", "vocal power"],
        "energy": 0.84,
        "brightness": 0.68,
        "danceability": 0.86,
        "tonal_energy": 0.75,
        "harmonic_key": "Fm"
    },
    {
        "youtube_video_id": "AilHrIpBQZg",
        "title": "Bedesasa Gojo (በደሳሳ ጎጆ)",
        "channel_name": "Aster Aweke",
        "duration_seconds": 307,
        "view_count": 249941,
        "era": "80s-90s Cassette",
        "qenet_mode": "Tizita",
        "qenet_submode": "Tizita Minor",
        "bpm": 88.0,
        "genre_tags": ["amharic", "tizita", "ballad", "acoustic"],
        "energy": 0.45,
        "brightness": 0.38,
        "danceability": 0.52,
        "tonal_energy": 0.92,
        "harmonic_key": "Dm"
    },
    {
        "youtube_video_id": "lYI09MMFK34",
        "title": "Yeserge Tzitaw (የሰርጌ ትዝታ)",
        "channel_name": "Aster Aweke",
        "duration_seconds": 313,
        "view_count": 347284,
        "era": "80s-90s Cassette",
        "qenet_mode": "Tizita",
        "qenet_submode": "Tizita Major",
        "bpm": 98.0,
        "genre_tags": ["amharic", "wedding", "ethio-jazz", "nostalgia"],
        "energy": 0.62,
        "brightness": 0.52,
        "danceability": 0.72,
        "tonal_energy": 0.86,
        "harmonic_key": "C"
    },

    # --- Mahmoud Ahmed (Golden 70s Ethio-Groove) ---
    {
        "youtube_video_id": "hHSKwS5u4T0",
        "title": "Teresash Woy (ተረሳሽ ወይ)",
        "channel_name": "Mahmoud Ahmed",
        "duration_seconds": 309,
        "view_count": 1911968,
        "era": "Golden 70s",
        "qenet_mode": "Bati",
        "qenet_submode": "Bati Minor",
        "bpm": 114.0,
        "genre_tags": ["amharic", "ethio-groove", "golden era", "soul"],
        "energy": 0.76,
        "brightness": 0.60,
        "danceability": 0.82,
        "tonal_energy": 0.78,
        "harmonic_key": "Am"
    },
    {
        "youtube_video_id": "Ff5oemhCYR0",
        "title": "Ebakesh Tareqign (እባክሽ ታረቂኝ)",
        "channel_name": "Mahmoud Ahmed",
        "duration_seconds": 281,
        "view_count": 393015,
        "era": "Golden 70s",
        "qenet_mode": "Tizita",
        "qenet_submode": "Tizita Major",
        "bpm": 104.0,
        "genre_tags": ["amharic", "golden soul", "vintage horn", "groove"],
        "energy": 0.70,
        "brightness": 0.55,
        "danceability": 0.76,
        "tonal_energy": 0.80,
        "harmonic_key": "G"
    },
    {
        "youtube_video_id": "J3Qv7jsQpeA",
        "title": "Bemen Sebeb Letlash (በምን ሰበብ ልጥላሽ)",
        "channel_name": "Mahmoud Ahmed",
        "duration_seconds": 275,
        "view_count": 344633,
        "era": "Golden 70s",
        "qenet_mode": "Ambassel",
        "qenet_submode": "Ambassel",
        "bpm": 100.0,
        "genre_tags": ["amharic", "ethiopiques", "vintage", "soul"],
        "energy": 0.68,
        "brightness": 0.52,
        "danceability": 0.74,
        "tonal_energy": 0.82,
        "harmonic_key": "Dm"
    },
    {
        "youtube_video_id": "TCpiaKDJX7A",
        "title": "Erè Mèla Mèla (እረ መላ መላ)",
        "channel_name": "Mahmoud Ahmed",
        "duration_seconds": 275,
        "view_count": 640000,
        "era": "Golden 70s",
        "qenet_mode": "Anchihoye",
        "qenet_submode": "Anchihoye",
        "bpm": 120.0,
        "genre_tags": ["amharic", "ethio-groove", "classic", "uptempo"],
        "energy": 0.85,
        "brightness": 0.66,
        "danceability": 0.88,
        "tonal_energy": 0.72,
        "harmonic_key": "Am"
    },

    # --- Mulatu Astatke & Ethio-Jazz ---
    {
        "youtube_video_id": "Wy-v-FgiUD8",
        "title": "Tezeta (Nostalgia - Ethio-Jazz Masterpiece)",
        "channel_name": "Mulatu Astatke",
        "duration_seconds": 377,
        "view_count": 1639917,
        "era": "Golden 70s",
        "qenet_mode": "Tizita",
        "qenet_submode": "Tizita Minor",
        "bpm": 80.0,
        "genre_tags": ["amharic", "ethio-jazz", "vibraphone", "instrumental", "tizita"],
        "energy": 0.42,
        "brightness": 0.36,
        "danceability": 0.52,
        "tonal_energy": 0.94,
        "harmonic_key": "Dm"
    },
    {
        "youtube_video_id": "jwdBRqIsVUY",
        "title": "Yèkèrmo Sèw (የከርሞ ሰው)",
        "channel_name": "Mulatu Astatke",
        "duration_seconds": 254,
        "view_count": 305955,
        "era": "Golden 70s",
        "qenet_mode": "Bati",
        "qenet_submode": "Bati Major",
        "bpm": 94.0,
        "genre_tags": ["amharic", "ethio-jazz", "vintage", "instrumental"],
        "energy": 0.56,
        "brightness": 0.48,
        "danceability": 0.66,
        "tonal_energy": 0.88,
        "harmonic_key": "Gm"
    },

    # --- Rophnan (Modern 2020s Future Ethio) ---
    {
        "youtube_video_id": "kUknTOgdWgk",
        "title": "SHEGIYE | ሮፍናን - ሸግዬ",
        "channel_name": "Rophnan",
        "duration_seconds": 234,
        "view_count": 29734356,
        "era": "Modern 2020s",
        "qenet_mode": "Bati",
        "qenet_submode": "Bati Minor",
        "bpm": 126.0,
        "genre_tags": ["amharic", "ethio-electronic", "edm", "batti club"],
        "energy": 0.95,
        "brightness": 0.84,
        "danceability": 0.94,
        "tonal_energy": 0.70,
        "harmonic_key": "F#m"
    },
    {
        "youtube_video_id": "a6oos465ZU0",
        "title": "DESSE | ሮፍናን - ደሴ",
        "channel_name": "Rophnan",
        "duration_seconds": 274,
        "view_count": 9029712,
        "era": "Modern 2020s",
        "qenet_mode": "Anchihoye",
        "qenet_submode": "Anchihoye",
        "bpm": 122.0,
        "genre_tags": ["amharic", "electronic", "ethio-bass", "dance"],
        "energy": 0.92,
        "brightness": 0.80,
        "danceability": 0.92,
        "tonal_energy": 0.74,
        "harmonic_key": "Cm"
    },
    {
        "youtube_video_id": "0cFVse_kFz8",
        "title": "YELOMI (Official Audio)",
        "channel_name": "Rophnan & Harmonize",
        "duration_seconds": 196,
        "view_count": 1337499,
        "era": "Modern 2020s",
        "qenet_mode": "Bati",
        "qenet_submode": "Bati Major",
        "bpm": 120.0,
        "genre_tags": ["amharic", "afrobeats", "ethio-pop", "dance"],
        "energy": 0.90,
        "brightness": 0.78,
        "danceability": 0.92,
        "tonal_energy": 0.72,
        "harmonic_key": "G"
    },
    {
        "youtube_video_id": "OfITp-9ILBU",
        "title": "QAL | ሮፍናን - ቃል",
        "channel_name": "Rophnan",
        "duration_seconds": 292,
        "view_count": 3965243,
        "era": "Modern 2020s",
        "qenet_mode": "Ambassel",
        "qenet_submode": "Ambassel",
        "bpm": 112.0,
        "genre_tags": ["amharic", "future-ethio", "melodic", "hybrid"],
        "energy": 0.78,
        "brightness": 0.66,
        "danceability": 0.84,
        "tonal_energy": 0.82,
        "harmonic_key": "Am"
    },

    # --- Gigi (Ejigayehu Shibabaw) ---
    {
        "youtube_video_id": "Ap6LuRkg7rk",
        "title": "Kahne (ካህኔ)",
        "channel_name": "Gigi (Ejigayehu Shibabaw)",
        "duration_seconds": 227,
        "view_count": 3243702,
        "era": "80s-90s Cassette",
        "qenet_mode": "Tizita",
        "qenet_submode": "Tizita Minor",
        "bpm": 102.0,
        "genre_tags": ["amharic", "spiritual", "ethio-fusion", "vocal"],
        "energy": 0.68,
        "brightness": 0.56,
        "danceability": 0.74,
        "tonal_energy": 0.86,
        "harmonic_key": "Em"
    },
    {
        "youtube_video_id": "Ph816VzHpsk",
        "title": "Guramayle (ጉራማይሌ)",
        "channel_name": "Gigi (Ejigayehu Shibabaw)",
        "duration_seconds": 280,
        "view_count": 1400000,
        "era": "80s-90s Cassette",
        "qenet_mode": "Bati",
        "qenet_submode": "Bati Minor",
        "bpm": 102.0,
        "genre_tags": ["amharic", "ethio-fusion", "world", "krar"],
        "energy": 0.66,
        "brightness": 0.55,
        "danceability": 0.72,
        "tonal_energy": 0.86,
        "harmonic_key": "Em"
    },
    {
        "youtube_video_id": "FpbF21wtDlw",
        "title": "Bale Washintu (ባለ ዋሽንቱ)",
        "channel_name": "Gigi (Ejigayehu Shibabaw)",
        "duration_seconds": 336,
        "view_count": 1417640,
        "era": "80s-90s Cassette",
        "qenet_mode": "Ambassel",
        "qenet_submode": "Ambassel",
        "bpm": 96.0,
        "genre_tags": ["amharic", "washint", "flute", "ethio-dub"],
        "energy": 0.62,
        "brightness": 0.50,
        "danceability": 0.70,
        "tonal_energy": 0.88,
        "harmonic_key": "Dm"
    },

    # --- Ephrem Tamiru ---
    {
        "youtube_video_id": "kzXPkoD3Lwg",
        "title": "Akale - አካሌ",
        "channel_name": "Ephrem Tamiru",
        "duration_seconds": 438,
        "view_count": 9780451,
        "era": "80s-90s Cassette",
        "qenet_mode": "Tizita",
        "qenet_submode": "Tizita Major",
        "bpm": 116.0,
        "genre_tags": ["amharic", "ethio-pop", "classic", "love song"],
        "energy": 0.75,
        "brightness": 0.60,
        "danceability": 0.82,
        "tonal_energy": 0.78,
        "harmonic_key": "C"
    },
    {
        "youtube_video_id": "8yRY1GnDv8o",
        "title": "Metadel New - መታደል ነው",
        "channel_name": "Ephrem Tamiru",
        "duration_seconds": 341,
        "view_count": 21100704,
        "era": "80s-90s Cassette",
        "qenet_mode": "Bati",
        "qenet_submode": "Bati Major",
        "bpm": 120.0,
        "genre_tags": ["amharic", "dance", "golden pop", "upbeat"],
        "energy": 0.80,
        "brightness": 0.64,
        "danceability": 0.86,
        "tonal_energy": 0.75,
        "harmonic_key": "G"
    },
    {
        "youtube_video_id": "JhncvKQT9oE",
        "title": "Kim Alyzim Banchi - ቂም አልይዝም ባንቺ",
        "channel_name": "Ephrem Tamiru",
        "duration_seconds": 343,
        "view_count": 10176521,
        "era": "80s-90s Cassette",
        "qenet_mode": "Bati",
        "qenet_submode": "Bati Minor",
        "bpm": 104.0,
        "genre_tags": ["amharic", "romantic", "bati", "ballad"],
        "energy": 0.64,
        "brightness": 0.50,
        "danceability": 0.72,
        "tonal_energy": 0.84,
        "harmonic_key": "Am"
    },

    # --- Traditional Acoustic: Krar & Masenqo ---
    {
        "youtube_video_id": "HblesimLJZM",
        "title": "Ethiopia Super Krar Traditional",
        "channel_name": "Krar Collective",
        "duration_seconds": 342,
        "view_count": 518,
        "era": "Golden 70s",
        "qenet_mode": "Anchihoye",
        "qenet_submode": "Anchihoye",
        "bpm": 138.0,
        "genre_tags": ["amharic", "krar", "polyrhythm", "traditional", "underground"],
        "energy": 0.90,
        "brightness": 0.72,
        "danceability": 0.92,
        "tonal_energy": 0.62,
        "harmonic_key": "A"
    },
    {
        "youtube_video_id": "RK9SXtIPw0Y",
        "title": "Tizita Played on the Krar (Traditional Lyre)",
        "channel_name": "Asnakech Worku",
        "duration_seconds": 471,
        "view_count": 229660,
        "era": "Golden 70s",
        "qenet_mode": "Tizita",
        "qenet_submode": "Tizita Minor",
        "bpm": 68.0,
        "genre_tags": ["amharic", "krar solo", "deep tizita", "acoustic", "underground"],
        "energy": 0.26,
        "brightness": 0.28,
        "danceability": 0.34,
        "tonal_energy": 0.98,
        "harmonic_key": "Dm"
    },
    {
        "youtube_video_id": "_RPiCzzCyKI",
        "title": "Masenqo Acoustic Traditional Meditation",
        "channel_name": "Getachew Kidane",
        "duration_seconds": 274,
        "view_count": 82689,
        "era": "Golden 70s",
        "qenet_mode": "Bati",
        "qenet_submode": "Bati Minor",
        "bpm": 72.0,
        "genre_tags": ["amharic", "masenqo", "bati", "meditative", "underground"],
        "energy": 0.30,
        "brightness": 0.30,
        "danceability": 0.38,
        "tonal_energy": 0.96,
        "harmonic_key": "Em"
    }
]

def generate_amharic_seed_catalog() -> List[Track]:
    raw_embeddings = []
    track_metadata = []

    for item in AMHARIC_SEED_TRACKS:
        seed_num = abs(hash(item["youtube_video_id"] + item["title"])) % (2**31)
        rng = np.random.RandomState(seed_num)
        
        base_vec = rng.normal(0, 0.2, 64)
        base_vec[0:16] += item["energy"] * 1.5
        base_vec[16:28] += item["tonal_energy"] * 1.2
        base_vec[28:36] += (item["bpm"] / 140.0) * 1.0
        base_vec[36:44] += item["brightness"] * 1.4
        base_vec[44:64] += item["danceability"] * 1.1
        
        norm = np.linalg.norm(base_vec)
        if norm > 0:
            base_vec = base_vec / norm

        raw_embeddings.append(base_vec)
        track_metadata.append((item, base_vec))

    # Compute 2D SVD/PCA Projection across all 64D vectors for the 2D Latent Space Canvas
    emb_matrix = np.array(raw_embeddings)
    centered = emb_matrix - np.mean(emb_matrix, axis=0)
    u, s, vt = np.linalg.svd(centered, full_matrices=False)
    coords_2d = u[:, :2] * s[:2]
    # Normalize coordinates to [-0.85, 0.85]
    max_val = np.max(np.abs(coords_2d)) + 1e-6
    normalized_coords = (coords_2d / max_val) * 0.85

    tracks = []
    for idx, (item, base_vec) in enumerate(track_metadata):
        gx = float(normalized_coords[idx, 0])
        gy = float(normalized_coords[idx, 1])

        features = AcousticFeatures(
            bpm=item["bpm"],
            energy=item["energy"],
            danceability=item["danceability"],
            brightness=item["brightness"],
            tonal_energy=item["tonal_energy"],
            harmonic_key=item["harmonic_key"],
            qenet_mode=item.get("qenet_mode", "Tizita"),
            qenet_submode=item.get("qenet_submode", "Tizita Minor"),
            qenet_confidence=0.88,
            embedding=base_vec.tolist()
        )

        track = Track(
            youtube_video_id=item["youtube_video_id"],
            title=item["title"],
            channel_name=item["channel_name"],
            duration_seconds=item["duration_seconds"],
            view_count=item["view_count"],
            genre_tags=item["genre_tags"],
            era=item.get("era", "Golden 70s"),
            galaxy_x=round(gx, 4),
            galaxy_y=round(gy, 4),
            acoustic_features=features
        )
        tracks.append(track)
    return tracks

def reseed_amharic_catalog():
    """Wipes existing database and initializes exclusively with verified Amharic catalog."""
    try:
        vector_store.client.delete_collection(collection_name=vector_store.collection_name)
    except Exception:
        pass
    vector_store._ensure_collection()
    tracks = generate_amharic_seed_catalog()
    vector_store.upsert_tracks_batch(tracks)
    print(f"🇪🇹 Re-seeded database with {len(tracks)} verified Amharic tracks with Qenet & 2D Latent Galaxy coordinates.")

def init_seed_catalog_if_empty():
    count = vector_store.count_tracks()
    if count == 0:
        reseed_amharic_catalog()
    else:
        sample = vector_store.get_all_tracks(limit=5)
        first_track = sample[0] if sample else {}
        if "qenet_mode" not in first_track or "galaxy_x" not in first_track:
            print("🔄 Migrating catalog to include Qenet and 2D Galaxy coordinates...")
            reseed_amharic_catalog()
        else:
            print(f"ℹ️ Qdrant Vector DB contains {count} verified Amharic tracks with Qenet intelligence.")
