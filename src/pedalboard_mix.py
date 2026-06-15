"""
pedalboard_mix.py — Advanced species mix pipeline using Spotify Pedalboard.

For each species:
  1. Pick longest MP3 from data/prototype/raw/<Species Name>/
  2. Find Suno track in output/suno/ (skip if missing)
  3. Clean bird recording with Pedalboard (HPF, LPF, compressor, reverb)
  4. Clean Suno track with Pedalboard (HPF, LPF, compressor, limiter)
  5. Apply dynamic volume arc to Suno track
  6. Place 8 bird clips with panning, random volume, no overlaps
  7. Add binaural beats (432 Hz L / 440 Hz R)
  8. Final master with Pedalboard (compressor, reverb, limiter, normalize)
  9. Export to output/final/v<n>_<YYYYMMDD_HHMMSS>/<species>_naturetunes.mp3

Versioned output folder — never overwrites existing runs.
"""

import random
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pedalboard as pb
from pedalboard.io import AudioFile
from pydub import AudioSegment

ROOT      = Path(__file__).parent.parent
RAW_DIR   = ROOT / "data" / "prototype" / "raw"
SUNO_DIR  = ROOT / "output" / "suno"
FINAL_DIR = ROOT / "output" / "final"

SAMPLE_RATE = 44100
CHANNELS    = 2
BITRATE     = "320k"

# Map slug → display name (folder name inside data/prototype/raw/)
SPECIES_MAP = {
    "hermit_thrush":      "Hermit Thrush",
    "common_nightingale": "Common Nightingale",
    "wood_thrush":        "Wood Thrush",
    "canyon_wren":        "Canyon Wren",
    "veery":              "Veery",
}

# Fuzzy keywords for matching Suno filenames to species


# Keyword sets — structured as (required, optional).
# A file matches only if it contains AT LEAST ONE required keyword.
# Optional keywords are ignored for matching (just for documentation).
SUNO_KEYWORDS: dict[str, list[str]] = {
    "hermit_thrush":      ["hermit", "thrush"],
    "common_nightingale": ["nightingale"],
    "wood_thrush":        ["wood thrush", "wood_thrush"],
    "canyon_wren":        ["canyon", "wren"],
    "veery":              ["veery", "twilight", "spiral"],
}

# Binaural beat frequencies
BINAURAL_LEFT_HZ  = 432.0
BINAURAL_RIGHT_HZ = 440.0
BINAURAL_DB       = -32

# Bird clip config — 8 clips
NUM_CLIPS   = 8
CLIP_PANS   = [-0.30, 0.30, 0.00, -0.30, 0.30, 0.00, -0.30, 0.00]  # L R C L R C L C
CLIP_DB_MIN = -13
CLIP_DB_MAX = -9
CLIP_LEN_MIN_MS = 4_000   # 4 s
CLIP_LEN_MAX_MS = 6_000   # 6 s
FADE_IN_MS  = 1_500
FADE_OUT_MS = 2_500

# Placement: evenly spaced at 12–15% of track duration, with random offset
SPACING_MIN_PCT = 0.12
SPACING_MAX_PCT = 0.15


# ── helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    return re.sub(r"[^\w]+", "_", text.lower()).strip("_")


def make_versioned_dir() -> Path:
    """Create output/final/v<n>_<YYYYMMDD_HHMMSS>/ — never overwrites."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    existing = sorted(FINAL_DIR.glob("v*_*/"), key=lambda p: p.name)
    next_n = len(existing) + 1
    folder = FINAL_DIR / f"v{next_n}_{ts}"
    folder.mkdir(parents=True, exist_ok=False)
    return folder


# ── pydub ↔ numpy / pedalboard bridges ───────────────────────────────────────

def seg_to_np(seg: AudioSegment) -> np.ndarray:
    """pydub AudioSegment → float32 numpy (channels, samples) for pedalboard."""
    seg = seg.set_sample_width(2).set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS)
    raw = np.frombuffer(seg.raw_data, dtype=np.int16).astype(np.float32) / 32768.0
    interleaved = raw.reshape(-1, CHANNELS)
    return interleaved.T.copy()           # (channels, samples)


def np_to_seg(arr: np.ndarray, frame_rate: int = SAMPLE_RATE) -> AudioSegment:
    """float32 numpy (channels, samples) → pydub AudioSegment."""
    interleaved = np.clip(arr.T, -1.0, 1.0)   # (samples, channels)
    pcm = (interleaved * 32767).astype(np.int16)
    return AudioSegment(
        pcm.tobytes(),
        frame_rate=frame_rate,
        sample_width=2,
        channels=arr.shape[0],
    )


def load_seg(path: Path) -> AudioSegment:
    return (AudioSegment.from_file(str(path))
            .set_frame_rate(SAMPLE_RATE)
            .set_channels(CHANNELS))


def apply_pedalboard(seg: AudioSegment, board: pb.Pedalboard) -> AudioSegment:
    arr = seg_to_np(seg)
    processed = board(arr, SAMPLE_RATE)
    return np_to_seg(processed)


def normalize_seg(seg: AudioSegment, target_db: float) -> AudioSegment:
    if seg.dBFS == -float("inf"):
        return seg
    return seg.apply_gain(target_db - seg.dBFS)


# ── Step 1 — find longest raw MP3 ────────────────────────────────────────────

def find_longest_raw(species_slug: str) -> Path:
    folder_name = SPECIES_MAP[species_slug]
    raw_folder  = RAW_DIR / folder_name
    if not raw_folder.exists():
        raise FileNotFoundError(f"Raw folder not found: {raw_folder}")
    mp3s = list(raw_folder.glob("*.mp3"))
    if not mp3s:
        raise FileNotFoundError(f"No MP3s in {raw_folder}")
    return max(mp3s, key=lambda p: p.stat().st_size)


# ── Step 2 — find Suno track (fuzzy keyword match) ───────────────────────────

def find_suno(species_slug: str) -> Path | None:
    keywords = SUNO_KEYWORDS.get(species_slug, [])
    candidates = []
    for f in SUNO_DIR.glob("*.mp3"):
        name_lower = f.stem.lower()
        if any(kw in name_lower for kw in keywords):
            candidates.append(f)
    if not candidates:
        return None
    # Pick most recently modified if multiple match
    return max(candidates, key=lambda p: p.stat().st_mtime)


# ── Step 3 — clean bird recording ────────────────────────────────────────────

def clean_bird(seg: AudioSegment) -> AudioSegment:
    board = pb.Pedalboard([
        pb.HighpassFilter(cutoff_frequency_hz=800),
        pb.LowpassFilter(cutoff_frequency_hz=12_000),
        pb.Compressor(ratio=3.0, threshold_db=-20),
        pb.Reverb(room_size=0.3, wet_level=0.2, dry_level=0.8),
    ])
    cleaned = apply_pedalboard(seg, board)
    return normalize_seg(cleaned, -10)


# ── Step 4 — clean Suno track ────────────────────────────────────────────────

def clean_suno(seg: AudioSegment) -> AudioSegment:
    board = pb.Pedalboard([
        pb.HighpassFilter(cutoff_frequency_hz=60),
        pb.LowpassFilter(cutoff_frequency_hz=16_000),
        pb.Compressor(ratio=2.0, threshold_db=-18),
        pb.Limiter(threshold_db=-2),
    ])
    return apply_pedalboard(seg, board)


# ── Step 5 — dynamic volume arc on Suno ──────────────────────────────────────

def apply_dynamic_arc(seg: AudioSegment) -> AudioSegment:
    total_ms = len(seg)
    p70 = int(total_ms * 0.70)
    p85 = int(total_ms * 0.85)

    intro   = seg[:30_000].fade(from_gain=-24, to_gain=-6,
                                start=0, duration=30_000)
    hold    = seg[30_000:p70].apply_gain(-6)
    peak    = seg[p70:p85].apply_gain(-4)
    outro   = seg[p85:].fade(from_gain=-4, to_gain=-24,
                             start=0, duration=max(1, total_ms - p85))
    return intro + hold + peak + outro


# ── Step 6 — bird clips (8, evenly spaced, no overlaps) ──────────────────────

def make_bird_clips(bird: AudioSegment) -> list[AudioSegment]:
    """
    Build 8 clips, each a randomly selected 4–6 s window from the bird
    recording. Volume, pan, and length are randomised per clip.
    """
    bird_len_ms = len(bird)
    clips = []
    for pan in CLIP_PANS:
        clip_len_ms = random.randint(CLIP_LEN_MIN_MS, CLIP_LEN_MAX_MS)
        max_start   = max(0, bird_len_ms - clip_len_ms)
        start_ms    = random.randint(0, max_start) if max_start > 0 else 0
        clip = bird[start_ms : start_ms + clip_len_ms]
        clip = clip.apply_gain(random.uniform(CLIP_DB_MIN, CLIP_DB_MAX))
        clip = clip.pan(pan)
        clip = clip.fade_in(min(FADE_IN_MS,  len(clip) // 2))
        clip = clip.fade_out(min(FADE_OUT_MS, len(clip) // 2))
        clips.append(clip)
    return clips


def clip_positions(total_ms: int, clips: list[AudioSegment]) -> list[int]:
    """
    Space 8 clips evenly across the track (12–15% spacing), with a small
    random offset per slot. Guarantees no clip overlaps the previous one.
    """
    positions: list[int] = []
    cursor = 0
    for i, clip in enumerate(clips):
        spacing_ms = int(total_ms * random.uniform(SPACING_MIN_PCT, SPACING_MAX_PCT))
        pos = cursor + spacing_ms
        # Clamp so clip fits within the track
        pos = min(pos, total_ms - len(clip))
        pos = max(pos, cursor)        # never behind last clip's end
        positions.append(pos)
        cursor = pos + len(clip)     # next clip must start after this one ends
    return positions


def overlay_at(base: AudioSegment, clip: AudioSegment, pos_ms: int) -> AudioSegment:
    needed = pos_ms + len(clip)
    if needed > len(base):
        base = base + AudioSegment.silent(duration=needed - len(base),
                                          frame_rate=SAMPLE_RATE)
    return base.overlay(clip, position=pos_ms)


# ── Step 7 — binaural beats ───────────────────────────────────────────────────

def make_binaural(total_ms: int) -> AudioSegment:
    n_samples = int(SAMPLE_RATE * total_ms / 1000)
    t = np.linspace(0, total_ms / 1000, n_samples, endpoint=False)

    left  = np.sin(2 * np.pi * BINAURAL_LEFT_HZ  * t).astype(np.float32)
    right = np.sin(2 * np.pi * BINAURAL_RIGHT_HZ * t).astype(np.float32)

    stereo = np.stack([left, right])               # (2, samples)
    seg    = np_to_seg(stereo)

    gain = BINAURAL_DB - seg.dBFS
    return seg.apply_gain(gain)


# ── Step 8 — final master ─────────────────────────────────────────────────────

def master(seg: AudioSegment) -> AudioSegment:
    board = pb.Pedalboard([
        pb.Compressor(ratio=2.0, threshold_db=-16),
        pb.Reverb(room_size=0.2, wet_level=0.15, dry_level=0.85),
        pb.Limiter(threshold_db=-1),
    ])
    mastered = apply_pedalboard(seg, board)
    return normalize_seg(mastered, -6)


# ── per-species pipeline ──────────────────────────────────────────────────────

def process(species_slug: str, out_dir: Path) -> str:
    # Step 2 — check Suno first (cheap)
    suno_path = find_suno(species_slug)
    if suno_path is None:
        return f"[SKIP] {species_slug} → no Suno track found"

    print(f'[MATCHED] {species_slug} → "{suno_path.name}"')

    # Step 1 — longest raw recording
    bird_path = find_longest_raw(species_slug)

    # Load
    bird_raw = load_seg(bird_path)
    suno_raw = load_seg(suno_path)
    total_ms = len(suno_raw)

    # Step 3 — clean bird
    bird_clean = clean_bird(bird_raw)

    # Step 4 — clean Suno
    suno_clean = clean_suno(suno_raw)

    # Step 5 — dynamic arc
    suno_arc = apply_dynamic_arc(suno_clean)

    # Step 6 — bird clips overlay
    clips     = make_bird_clips(bird_clean)
    positions = clip_positions(total_ms, clips)
    mix = suno_arc
    for clip, pos in zip(clips, positions):
        mix = overlay_at(mix, clip, pos)

    # Step 7 — binaural beats
    binaural = make_binaural(len(mix))
    mix = mix.overlay(binaural)

    # Step 8 — master
    final = master(mix)

    # Export
    out_path = out_dir / f"{species_slug}_naturetunes.mp3"
    final.export(str(out_path), format="mp3", bitrate=BITRATE)

    rel = out_path.relative_to(ROOT)
    return f"[OK] {species_slug} → {rel}"


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    random.seed()
    out_dir = make_versioned_dir()
    print(f"\npedalboard_mix — output → {out_dir.relative_to(ROOT)}\n")

    for slug in SPECIES_MAP:
        try:
            msg = process(slug, out_dir)
        except Exception as exc:
            msg = f"[ERR] {slug} → {exc}"
        print(msg)

    print()


if __name__ == "__main__":
    main()
