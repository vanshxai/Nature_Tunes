#!/usr/bin/env python3
"""BirdMind asset preparer.

Extracts one clean 20-second clip per species (best onset window of the
cleanest recording) and generates 3 programmatic beat loops, all ready for
browser playback via Tone.js.

Outputs:
  frontend/public/audio/birds/<species_id>.mp3   (17 bird clips)
  frontend/public/audio/beats/soft_beat.mp3
  frontend/public/audio/beats/tribal_beat.mp3
  frontend/public/audio/beats/electronic_beat.mp3
  frontend/public/audio/manifest.json

Conda env: birdmind
    conda activate birdmind
    python src/prepare_assets.py
"""

import json
import re
import sys
import warnings
from pathlib import Path

import librosa
import numpy as np
import pandas as pd
from pydub import AudioSegment

warnings.filterwarnings("ignore")

# ── Point pydub at conda env ffmpeg (not always on PATH) ─────────────────────
_ffmpeg = Path(sys.executable).parent / "ffmpeg"
if _ffmpeg.exists():
    AudioSegment.converter = str(_ffmpeg)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "prototype" / "prototype_metadata.csv"
BIRDS_DIR = BASE_DIR / "frontend" / "public" / "audio" / "birds"
BEATS_DIR = BASE_DIR / "frontend" / "public" / "audio" / "beats"

# ── Constants ─────────────────────────────────────────────────────────────────
SR = 22050
CLIP_S = 20
WINDOW_STEP_S = 1
FADE_IN_S = 0.3
FADE_OUT_S = 1.0
PEAK_AMP = 0.85
BEAT_S = 8          # beat loop length
BPM = 75
MP3_BITRATE = "128k"


# ── Helpers ───────────────────────────────────────────────────────────────────

def species_id(common_name: str) -> str:
    """'Common Nightingale' -> 'common_nightingale'"""
    return re.sub(r"[^a-z0-9]+", "_", common_name.lower()).strip("_")


def apply_fades(y: np.ndarray, sr: int,
                fade_in_s: float, fade_out_s: float) -> np.ndarray:
    n_in = min(int(fade_in_s * sr), len(y))
    n_out = min(int(fade_out_s * sr), len(y))
    y = y.copy()
    if n_in > 0:
        y[:n_in] *= np.linspace(0.0, 1.0, n_in, dtype=np.float32)
    if n_out > 0:
        y[-n_out:] *= np.linspace(1.0, 0.0, n_out, dtype=np.float32)
    return y


def normalize(y: np.ndarray, peak: float = 0.85) -> np.ndarray:
    m = np.max(np.abs(y))
    return y / m * peak if m > 0 else y


def numpy_to_mp3(y: np.ndarray, sr: int, out_path: Path,
                 bitrate: str = "128k") -> None:
    """Write float32 numpy array as MP3 via a temporary WAV."""
    pcm = (np.clip(y, -1.0, 1.0) * 32767).astype(np.int16)
    seg = AudioSegment(
        pcm.tobytes(),
        frame_rate=sr,
        sample_width=2,
        channels=1,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seg.export(str(out_path), format="mp3", bitrate=bitrate)


# ── Bird clip extraction ──────────────────────────────────────────────────────

def best_window(y: np.ndarray, sr: int, clip_samples: int,
                step_samples: int) -> tuple[int, int]:
    """Return (start_sample, onset_count) for the 20s window with most onsets."""
    total = len(y)
    if total <= clip_samples:
        # File too short — use the whole thing
        onsets = librosa.onset.onset_detect(y=y, sr=sr,
                                             backtrack=True, units="time")
        return 0, len(onsets)

    best_start = 0
    best_count = -1
    start = 0
    while start + clip_samples <= total:
        window = y[start: start + clip_samples]
        onsets = librosa.onset.onset_detect(y=window, sr=sr,
                                             backtrack=True, units="time")
        if len(onsets) > best_count:
            best_count = len(onsets)
            best_start = start
        start += step_samples
    return best_start, best_count


def extract_bird_clip(row: pd.Series) -> tuple[np.ndarray, float, int, float]:
    """Load file, find best window, fade + normalise.

    Returns (audio_array, window_start_s, onset_count, onset_density_of_window)
    """
    fpath = BASE_DIR / row["file_path"]
    y, sr = librosa.load(str(fpath), sr=SR, mono=True)

    clip_samples = int(CLIP_S * SR)
    step_samples = int(WINDOW_STEP_S * SR)

    start_sample, n_onsets = best_window(y, sr, clip_samples, step_samples)
    end_sample = min(start_sample + clip_samples, len(y))
    clip = y[start_sample:end_sample].astype(np.float32)

    # Pad with silence if clip shorter than 20s (very short source file)
    if len(clip) < clip_samples:
        clip = np.pad(clip, (0, clip_samples - len(clip)))

    clip = apply_fades(clip, SR, FADE_IN_S, FADE_OUT_S)
    clip = normalize(clip, PEAK_AMP)

    window_start_s = start_sample / SR
    clip_duration = len(clip) / SR
    onset_density_window = n_onsets / clip_duration if clip_duration > 0 else 0.0
    return clip, window_start_s, n_onsets, onset_density_window


# ── Beat synthesis ────────────────────────────────────────────────────────────

def make_sine(freq: float, dur_s: float, sr: int,
              amp: float = 1.0) -> np.ndarray:
    t = np.linspace(0, dur_s, int(dur_s * sr), endpoint=False)
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def make_noise_burst(dur_s: float, sr: int, amp: float = 1.0) -> np.ndarray:
    n = int(dur_s * sr)
    return (amp * np.random.uniform(-1, 1, n)).astype(np.float32)


def apply_env(y: np.ndarray, attack_s: float = 0.003,
              decay_s: float = 0.08, sr: int = SR) -> np.ndarray:
    """Simple attack-decay envelope."""
    n_a = min(int(attack_s * sr), len(y))
    n_d = min(int(decay_s * sr), len(y))
    env = np.zeros(len(y), dtype=np.float32)
    if n_a > 0:
        env[:n_a] = np.linspace(0, 1, n_a)
    tail = len(y) - n_a
    d_actual = min(n_d, tail)
    if d_actual > 0:
        env[n_a: n_a + d_actual] = np.linspace(1, 0, d_actual)
    return y * env


def beat_grid(bpm: int, duration_s: float, sr: int) -> list[int]:
    """Beat positions in samples for given BPM."""
    beat_interval = 60.0 / bpm
    positions = []
    t = 0.0
    while t < duration_s:
        positions.append(int(t * sr))
        t += beat_interval
    return positions


def place_hit(mix: np.ndarray, hit: np.ndarray, pos: int) -> None:
    end = min(pos + len(hit), len(mix))
    length = end - pos
    if length > 0:
        mix[pos:end] += hit[:length]


def synthesise_kick_sine(freq: float = 80.0, pitch_drop: float = 40.0,
                          dur_s: float = 0.25, amp: float = 1.0) -> np.ndarray:
    """Sine kick with frequency envelope (pitch drop)."""
    n = int(dur_s * SR)
    t = np.linspace(0, dur_s, n, endpoint=False)
    # Exponential pitch drop
    freq_env = freq * np.exp(-pitch_drop * t)
    phase = np.cumsum(2 * np.pi * freq_env / SR)
    hit = (amp * np.sin(phase)).astype(np.float32)
    return apply_env(hit, attack_s=0.002, decay_s=0.15)


def synthesise_hihat(dur_s: float = 0.04, amp: float = 0.4,
                      bright: bool = True) -> np.ndarray:
    """White-noise hi-hat with fast decay."""
    hit = make_noise_burst(dur_s, SR, amp)
    if bright:
        # Simple high-pass: diff approximation
        hit = np.diff(np.pad(hit, (1, 0))).astype(np.float32)
    return apply_env(hit, attack_s=0.001, decay_s=0.03)


def make_soft_beat(duration_s: float, bpm: int) -> np.ndarray:
    """Gentle shaker feel — sine kick on 1&3, hi-hat every beat."""
    n = int(duration_s * SR)
    mix = np.zeros(n, dtype=np.float32)
    beats = beat_grid(bpm, duration_s, SR)

    kick = synthesise_kick_sine(freq=70, pitch_drop=35, dur_s=0.22, amp=0.8)
    hat = synthesise_hihat(dur_s=0.05, amp=0.3, bright=False)

    for i, pos in enumerate(beats):
        if i % 4 in (0, 2):           # beats 1 and 3 (0-indexed 0 and 2)
            place_hit(mix, kick, pos)
        place_hit(mix, hat, pos)       # hi-hat every beat

    return normalize(mix, 0.70)


def make_tribal_beat(duration_s: float, bpm: int) -> np.ndarray:
    """Deeper, syncopated pattern — low kick, off-beat accents."""
    n = int(duration_s * SR)
    mix = np.zeros(n, dtype=np.float32)
    beats = beat_grid(bpm, duration_s, SR)

    # Low thudding kick
    kick = synthesise_kick_sine(freq=55, pitch_drop=25, dur_s=0.30, amp=0.9)
    # Mid accent hit (slightly higher freq)
    accent = synthesise_kick_sine(freq=120, pitch_drop=50, dur_s=0.15, amp=0.5)
    hat = synthesise_hihat(dur_s=0.06, amp=0.25, bright=False)

    beat_s = 60.0 / bpm
    sixteenth = int(beat_s / 4 * SR)

    for i, pos in enumerate(beats):
        # Kick on 1 and 2.5 (syncopated)
        if i % 4 == 0:
            place_hit(mix, kick, pos)
        if i % 4 == 2:
            place_hit(mix, kick, pos)
        # Syncopated accent: sixteenth before beat 3
        if i % 4 == 2:
            place_hit(mix, accent, max(0, pos - sixteenth))
        # Hi-hat on beats 2 and 4
        if i % 4 in (1, 3):
            place_hit(mix, hat, pos)

    return normalize(mix, 0.75)


def make_electronic_beat(duration_s: float, bpm: int) -> np.ndarray:
    """Tight 4-on-floor kick, crisp hi-hat every 8th note."""
    n = int(duration_s * SR)
    mix = np.zeros(n, dtype=np.float32)
    beats = beat_grid(bpm, duration_s, SR)

    # Punchy electronic kick — faster pitch drop
    kick = synthesise_kick_sine(freq=90, pitch_drop=55, dur_s=0.20, amp=1.0)
    # Crisp bright hat
    hat_on = synthesise_hihat(dur_s=0.035, amp=0.45, bright=True)
    hat_off = synthesise_hihat(dur_s=0.025, amp=0.25, bright=True)  # weaker off-beats

    beat_s = 60.0 / bpm
    eighth_offset = int(beat_s / 2 * SR)

    for i, pos in enumerate(beats):
        # 4-on-floor: kick every beat
        place_hit(mix, kick, pos)
        # Hat on every beat
        place_hit(mix, hat_on, pos)
        # Hat on every 8th-note off-beat
        off = pos + eighth_offset
        if off < n:
            place_hit(mix, hat_off, off)

    return normalize(mix, 0.80)


# ── suggested_role logic ──────────────────────────────────────────────────────

def suggested_role(onset_density: float, onset_interval_ms: float) -> str:
    if onset_density > 3.0:
        return "texture"
    if onset_interval_ms > 600:
        return "anchor"
    return "melody"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("BirdMind Asset Preparer")
    print("=" * 60)

    df = pd.read_csv(CSV_PATH)
    df = df[df["usable"] == True].copy()  # noqa: E712
    print(f"Loaded {len(df)} usable rows across {df.common_name.nunique()} species\n")

    # ── Bird clips ────────────────────────────────────────────────────────────
    BIRDS_DIR.mkdir(parents=True, exist_ok=True)
    bird_manifest = []

    for species in sorted(df.common_name.unique()):
        group = df[df.common_name == species].sort_values("silence_ratio")
        sid = species_id(species)
        out_path = BIRDS_DIR / f"{sid}.mp3"

        selected = None
        for _, row in group.iterrows():
            fpath = BASE_DIR / row["file_path"]
            if fpath.exists():
                selected = row
                break

        if selected is None:
            print(f"  [SKIP] {species} — no readable file found")
            continue

        try:
            clip, win_start_s, n_onsets, win_density = extract_bird_clip(selected)
            numpy_to_mp3(clip, SR, out_path, bitrate=MP3_BITRATE)

            row_density = float(selected["onset_density"])
            row_interval = float(selected["onset_interval_ms"]) \
                if not np.isnan(selected["onset_interval_ms"]) else 9999.0
            role = suggested_role(row_density, row_interval)

            print(
                f"  {species:<28}  XC#{int(selected['xc_id']):<8}"
                f"  win_start={win_start_s:5.1f}s  "
                f"onsets_in_win={n_onsets:3d}  "
                f"win_density={win_density:.2f}/s  "
                f"role={role}"
            )

            bird_manifest.append({
                "id": sid,
                "common_name": species,
                "file": f"/audio/birds/{sid}.mp3",
                "dominant_freq_hz": round(float(selected["dominant_freq_hz"]), 0),
                "onset_density": round(row_density, 2),
                "onset_interval_ms": round(row_interval, 1)
                    if row_interval < 9999 else None,
                "suggested_role": role,
            })
        except Exception as exc:
            print(f"  [ERROR] {species}: {exc}")

    # ── Beat loops ────────────────────────────────────────────────────────────
    print("\nGenerating beat loops …")
    BEATS_DIR.mkdir(parents=True, exist_ok=True)

    beats = {
        "soft_beat":       (make_soft_beat,       "Soft"),
        "tribal_beat":     (make_tribal_beat,      "Tribal"),
        "electronic_beat": (make_electronic_beat,  "Electronic"),
    }
    beat_manifest = []
    for fname, (fn, display_name) in beats.items():
        beat_id = fname.replace("_beat", "")
        out_path = BEATS_DIR / f"{fname}.mp3"
        y = fn(BEAT_S, BPM)
        numpy_to_mp3(y, SR, out_path, bitrate=MP3_BITRATE)
        size_kb = out_path.stat().st_size // 1024
        print(f"  {fname}.mp3  ({size_kb} KB, {BEAT_S}s @ {BPM} BPM)")
        beat_manifest.append({
            "id": beat_id,
            "name": display_name,
            "file": f"/audio/beats/{fname}.mp3",
        })

    # ── manifest.json ─────────────────────────────────────────────────────────
    manifest_path = BASE_DIR / "frontend" / "public" / "audio" / "manifest.json"
    manifest = {"birds": bird_manifest, "beats": beat_manifest}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\nmanifest.json  ({len(bird_manifest)} birds, {len(beat_manifest)} beats)")
    print(f"  -> {manifest_path.relative_to(BASE_DIR)}")

    print("\n" + "=" * 60)
    print(f"Done. Bird clips: {BIRDS_DIR.relative_to(BASE_DIR)}")
    print(f"      Beats:      {BEATS_DIR.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
