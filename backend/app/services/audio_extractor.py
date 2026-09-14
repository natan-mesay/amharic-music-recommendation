"""
Audio Feature Extraction and Acoustic Embedding Pipeline.
Enhanced with Ethiopian Qenet (ቅኝት) Pentatonic Modal Scale Classification.
Computes multi-window acoustic descriptors:
- Ethiopian Pentatonic Scale Identification (Tizita, Bati, Ambassel, Anchihoye)
- Timbral brightness (Spectral Centroid)
- Frequency energy distribution (Mel-Filterbank bands)
- Harmonic Chroma Pitch Profiles (12-semitone tonality)
- Rhythmic Onset & BPM (Autocorrelation Tempogram)
- Dynamic Texture & RMS Energy
"""
import numpy as np
from scipy.signal import spectrogram
from typing import Dict, Any, List, Tuple
from ..config import settings
from ..models.schemas import AcousticFeatures

# Ethiopian 5-Note Pentatonic Modal Scale Binary Templates across 12 chromatic pitches
# [C, C#, D, D#, E, F, F#, G, G#, A, A#, B]
ETHIOPIAN_QENET_TEMPLATES = {
    "Tizita Major": np.array([1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0], dtype=float),   # Intervals: 0, 2, 4, 7, 9
    "Tizita Minor": np.array([1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0], dtype=float),   # Intervals: 0, 3, 5, 7, 10
    "Bati Major":   np.array([1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 0, 1], dtype=float),   # Intervals: 0, 4, 5, 7, 11
    "Bati Minor":   np.array([1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0], dtype=float),   # Intervals: 0, 3, 5, 8, 10
    "Ambassel":     np.array([1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0], dtype=float),   # Intervals: 0, 1, 5, 7, 8
    "Anchihoye":    np.array([1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 0], dtype=float),   # Intervals: 0, 1, 5, 6, 10
}

QENET_PARENT_MAP = {
    "Tizita Major": "Tizita",
    "Tizita Minor": "Tizita",
    "Bati Major": "Bati",
    "Bati Minor": "Bati",
    "Ambassel": "Ambassel",
    "Anchihoye": "Anchihoye",
}

class AudioFeatureExtractor:
    def __init__(self, sample_rate: int = settings.SAMPLE_RATE, embedding_dim: int = settings.EMBEDDING_DIM):
        self.sample_rate = sample_rate
        self.embedding_dim = embedding_dim
        self.window_samples = int(settings.WINDOW_SEC * sample_rate)
        self.hop_samples = int(settings.HOP_SEC * sample_rate)

    def classify_qenet_from_chroma(self, chroma_vector: np.ndarray) -> Tuple[str, str, float]:
        """
        Classifies the Ethiopian pentatonic modal scale (Qenet) from a 12-tone chroma profile.
        Uses rotational invariance across all 12 pitch roots to match modal intervals.
        Returns: (qenet_mode, qenet_submode, confidence)
        """
        if len(chroma_vector) < 12:
            return "Tizita", "Tizita Minor", 0.5

        chroma_norm = chroma_vector[:12]
        c_len = np.linalg.norm(chroma_norm)
        if c_len > 0:
            chroma_norm = chroma_norm / c_len

        best_score = -1.0
        best_submode = "Tizita Minor"

        for submode, template in ETHIOPIAN_QENET_TEMPLATES.items():
            t_norm = template / np.linalg.norm(template)
            # Test all 12 circular pitch shifts (root key independence)
            for shift in range(12):
                rotated_t = np.roll(t_norm, shift)
                sim = float(np.dot(chroma_norm, rotated_t))
                if sim > best_score:
                    best_score = sim
                    best_submode = submode

        confidence = round(float(np.clip((best_score - 0.3) / 0.7, 0.5, 0.99)), 3)
        primary_mode = QENET_PARENT_MAP.get(best_submode, "Tizita")
        return primary_mode, best_submode, confidence

    def extract_features_from_audio(self, audio_data: np.ndarray, sr: int = None) -> AcousticFeatures:
        """
        Extract acoustic descriptors and 64-dimensional dense normalized embedding vector
        from an audio array, complete with Ethiopian Qenet classification.
        """
        if sr is not None and sr != self.sample_rate:
            num_target_samples = int(len(audio_data) * self.sample_rate / sr)
            audio_data = np.interp(
                np.linspace(0, len(audio_data), num_target_samples, endpoint=False),
                np.arange(len(audio_data)),
                audio_data
            )
        
        # Ensure mono float32 normalized [-1, 1]
        if audio_data.ndim > 1:
            audio_data = np.mean(audio_data, axis=1)
        if np.max(np.abs(audio_data)) > 0:
            audio_data = audio_data / np.max(np.abs(audio_data))
        
        total_samples = len(audio_data)
        if total_samples < self.sample_rate * 2:
            pad_len = self.sample_rate * 2 - total_samples
            audio_data = np.pad(audio_data, (0, pad_len), mode='constant')
            total_samples = len(audio_data)

        # 1. Multi-window slicing
        window_embeddings = []
        bpms = []
        energies = []
        brightnesses = []
        
        step = max(self.hop_samples, self.sample_rate * 5)
        for start_idx in range(0, max(1, total_samples - self.window_samples + 1), step):
            end_idx = min(start_idx + self.window_samples, total_samples)
            chunk = audio_data[start_idx:end_idx]
            if len(chunk) < self.sample_rate:
                break
            
            chunk_vec, chunk_bpm, chunk_nrg, chunk_brt = self._process_chunk(chunk)
            window_embeddings.append(chunk_vec)
            bpms.append(chunk_bpm)
            energies.append(chunk_nrg)
            brightnesses.append(chunk_brt)

        if not window_embeddings:
            chunk_vec, chunk_bpm, chunk_nrg, chunk_brt = self._process_chunk(audio_data)
            window_embeddings.append(chunk_vec)
            bpms.append(chunk_bpm)
            energies.append(chunk_nrg)
            brightnesses.append(chunk_brt)

        # 2. Hierarchical Temporal Pooling (Mean + Max pooling across windows)
        emb_matrix = np.array(window_embeddings)
        mean_emb = np.mean(emb_matrix, axis=0)
        max_emb = np.max(emb_matrix, axis=0)
        global_vec = 0.7 * mean_emb + 0.3 * max_emb
        norm = np.linalg.norm(global_vec)
        if norm > 0:
            global_vec = global_vec / norm

        avg_bpm = float(np.median(bpms))
        avg_energy = float(np.mean(energies))
        avg_brightness = float(np.mean(brightnesses))
        
        # Estimate danceability from rhythm regularity
        danceability = float(np.clip(1.0 - (np.std(bpms) / (avg_bpm + 1e-5)), 0.2, 0.95))
        tonal_energy = float(np.clip(np.mean(global_vec[16:28]) * 3.0, 0.1, 0.9))
        
        pitch_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        chroma_slice = global_vec[16:28]
        dominant_pitch_idx = int(np.argmax(chroma_slice))
        harmonic_key = pitch_names[dominant_pitch_idx]

        # Ethiopian Qenet classification from Chroma profile (dimensions 16..28)
        qenet_mode, qenet_submode, qenet_confidence = self.classify_qenet_from_chroma(chroma_slice)

        return AcousticFeatures(
            bpm=round(avg_bpm, 1),
            energy=round(avg_energy, 3),
            danceability=round(danceability, 3),
            brightness=round(avg_brightness, 3),
            tonal_energy=round(tonal_energy, 3),
            harmonic_key=harmonic_key,
            qenet_mode=qenet_mode,
            qenet_submode=qenet_submode,
            qenet_confidence=qenet_confidence,
            embedding=global_vec.tolist()
        )

    def _process_chunk(self, chunk: np.ndarray) -> Tuple[np.ndarray, float, float, float]:
        """
        Processes a single ~30s chunk into acoustic sub-features:
        - 16 Mel-frequency energy bins
        - 12 Chroma pitch energy classes
        - 8 Spectral contrast & roll-off bands
        - 8 Rhythmic pulse & tempogram features
        - 20 High-order harmonic timbre texture coefficients
        Total = 64 dimensions
        """
        nperseg = 1024
        noverlap = 512
        freqs, times, Sxx = spectrogram(chunk, fs=self.sample_rate, nperseg=nperseg, noverlap=noverlap)
        eps = 1e-10
        log_Sxx = np.log10(Sxx + eps)

        # 1. Energy & RMS
        rms_energy = float(np.sqrt(np.mean(chunk**2)))
        normalized_energy = float(np.clip(rms_energy * 3.0, 0.0, 1.0))

        # 2. Spectral Centroid (Brightness)
        freq_weights = freqs[:, np.newaxis]
        centroid = np.sum(freq_weights * Sxx, axis=0) / (np.sum(Sxx, axis=0) + eps)
        mean_centroid = float(np.mean(centroid))
        normalized_brightness = float(np.clip(mean_centroid / (self.sample_rate / 4), 0.0, 1.0))

        # 3. 16 Mel-scale Energy Bands (0 to 8000 Hz)
        mel_bins = np.linspace(20, freqs[-1], 17)
        mel_energies = []
        for i in range(16):
            mask = (freqs >= mel_bins[i]) & (freqs < mel_bins[i+1])
            if np.any(mask):
                mel_energies.append(np.mean(log_Sxx[mask, :]))
            else:
                mel_energies.append(0.0)
        mel_energies = np.array(mel_energies)
        mel_energies = (mel_energies - np.min(mel_energies)) / (np.ptp(mel_energies) + eps)

        # 4. 12-Tone Chroma Pitch Profile
        chroma = np.zeros(12)
        for i, f in enumerate(freqs):
            if f > 65.4:  # Above C2
                midi_val = int(round(12 * np.log2(f / 440.0) + 69)) % 12
                chroma[midi_val] += np.sum(Sxx[i, :])
        chroma = chroma / (np.sum(chroma) + eps)

        # 5. Rhythmic Onset & BPM Estimation via Autocorrelation
        onset_env = np.mean(np.diff(np.maximum(0, log_Sxx), axis=1, prepend=0), axis=0)
        onset_env = np.maximum(0, onset_env)
        
        if len(onset_env) > 10:
            autocorr = np.correlate(onset_env - np.mean(onset_env), onset_env - np.mean(onset_env), mode='full')
            autocorr = autocorr[len(autocorr)//2:]
            time_res = (len(chunk) / self.sample_rate) / len(times)
            min_lag = int((60.0 / 180.0) / time_res)
            max_lag = int((60.0 / 60.0) / time_res)
            if max_lag < len(autocorr) and min_lag < max_lag:
                peak_lag = min_lag + np.argmax(autocorr[min_lag:max_lag])
                est_bpm = 60.0 / (peak_lag * time_res)
            else:
                est_bpm = 120.0
        else:
            est_bpm = 120.0
            autocorr = np.zeros(8)
            
        rhythm_feats = autocorr[:8] if len(autocorr) >= 8 else np.pad(autocorr, (0, 8 - len(autocorr)))
        rhythm_feats = rhythm_feats / (np.linalg.norm(rhythm_feats) + eps)

        # 6. Spectral Contrast & Texture
        contrast_bands = []
        for i in range(8):
            band_mask = (freqs >= (i * 500)) & (freqs < ((i + 1) * 500))
            if np.any(band_mask):
                peak = np.percentile(log_Sxx[band_mask, :], 90)
                valley = np.percentile(log_Sxx[band_mask, :], 10)
                contrast_bands.append(peak - valley)
            else:
                contrast_bands.append(0.0)
        contrast_bands = np.array(contrast_bands)
        contrast_bands = contrast_bands / (np.linalg.norm(contrast_bands) + eps)

        # 7. Timbre Shape (Higher-order spectral distribution)
        timbre_slice = np.mean(log_Sxx[:20, :], axis=1) if log_Sxx.shape[0] >= 20 else np.pad(np.mean(log_Sxx, axis=1), (0, max(0, 20 - log_Sxx.shape[0])))
        timbre_slice = timbre_slice[:20]
        timbre_slice = (timbre_slice - np.mean(timbre_slice)) / (np.std(timbre_slice) + eps)

        # Assemble into 64-dim vector: 16 (Mel) + 12 (Chroma) + 8 (Rhythm) + 8 (Contrast) + 20 (Timbre) = 64
        feature_vec = np.concatenate([mel_energies, chroma, rhythm_feats, contrast_bands, timbre_slice])
        norm = np.linalg.norm(feature_vec)
        if norm > 0:
            feature_vec = feature_vec / norm

        return feature_vec, float(est_bpm), normalized_energy, normalized_brightness

extractor = AudioFeatureExtractor()
