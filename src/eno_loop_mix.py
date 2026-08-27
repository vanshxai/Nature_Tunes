"""
eno_loop_mix.py — Generative phasing experiment (Eno / Riley method)

Three audio loops with mutually prime-ish lengths phase against each other
over 4 minutes, producing a texture that never exactly repeats.

  Bird seed   → loops every 17 s
  Melody stem → loops every 23 s  (Suno file, heavily LPF'd as a diffuse layer)
  String pad  → loops every 31 s  (synthesised harmonic pad)

Usage:
  python src/eno_loop_mix.py [species_slug]

If no slug given, defaults to hermit_thrush.
"""

import sys
import math
import random
import argparse
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfilt
from pydub import AudioSegment
from pydub.generators import Sine

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent.parent
SEEDS_DIR = ROOT / "output" / "seeds"
SUNO_DIR  = ROOT / "output" / "suno"
OUT_DIR   = ROOT / "output" / "experimental"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── timing constants ──────────────────────────────────────────────────────────
BIRD_LOOP_S    = 17        # seconds — prime-ish trio
MELODY_LOOP_S  = 23
PAD_LOOP_S     = 31
TOTAL_S        = 4 * 60   # 4 minutes
FADE_IN_S      = 20
FADE_OUT_S     = 20
SAMPLE_RATE    = 44100
CHANNELS       = 2

# ── volume levels (dBFS relative) ────────────────────────────────────────────
BIRD_DB    = -12.0
MELODY_DB  = -18.0   # Suno mix is busy — keep it well back
PAD_DB     = -14.0

# ── Suno keyword map (same as pedalboard_mix) ────────────────────────────────
SUNO_KEYWORDS = {
    "hermit_thrush":      ["hermit", "thrush"],
    "common_nightingale": ["nightingale"],
    "wood_thrush":        ["wood thrush", "wood_thrush"],
    "canyon_wren":        ["canyon", "wren"],
    "veery":              ["veery", "twilight", "spiral"],
}

# ── helpers ───────────────────────────────────────────────────────────────────

def seg_to_np(seg: AudioSegment) -> np.ndarray:
    """AudioSegment → float32 (samples, channels)"""
    raw = np.frombuffer(seg.raw_data, dtype=np.int16).astype(np.float32) / 32768.0
    return raw.reshape(-1, seg.channels)

def np_to_seg(arr: np.ndarray, frame_rate: int = SAMPLE_RATE) -> AudioSegment:
    """float32 (samples, channels) → AudioSegment"""
    clipped = np.clip(arr, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16).tobytes()
    return AudioSegment(pcm, frame_rate=frame_rate,
                        sample_width=2, channels=arr.shape[1])

def to_stereo_44k(seg: AudioSegment) -> AudioSegment:
    return seg.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS).set_sample_width(2)

def butter_lpf(arr: np.ndarray, cutoff_hz: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    nyq = sr / 2.0
    sos = butter(5, cutoff_hz / nyq, btype="low", output="sos")
    return sosfilt(sos, arr, axis=0)

def butter_hpf(arr: np.ndarray, cutoff_hz: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    nyq = sr / 2.0
    sos = butter(5, cutoff_hz / nyq, btype="high", output="sos")
    return sosfilt(sos, arr, axis=0)


def make_loop(seg: AudioSegment, loop_s: int, total_s: int) -> AudioSegment:
    """Tile `seg` (trimmed/padded to loop_s) to fill total_s exactly."""
    loop_ms  = loop_s  * 1000
    total_ms = total_s * 1000

    # Fit source into the loop window
    if len(seg) >= loop_ms:
        cell = seg[:loop_ms]
    else:
        silence = AudioSegment.silent(duration=loop_ms - len(seg),
                                      frame_rate=SAMPLE_RATE)
        cell = seg + silence

    # Tile
    reps = math.ceil(total_ms / loop_ms)
    tiled = cell * reps
    return tiled[:total_ms]


def find_suno(slug: str) -> Path | None:
    keywords = SUNO_KEYWORDS.get(slug, [slug.replace("_", " ")])
    candidates = [
        f for f in SUNO_DIR.iterdir()
        if f.suffix.lower() in (".mp3", ".wav", ".flac")
        and any(kw in f.name.lower() for kw in keywords)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.stat().st_mtime)


def make_pad_np(total_s: int, loop_s: int,
                root_hz: float = 220.0) -> np.ndarray:
    """
    Synthesise a slow string-pad: stacked harmonics (1st, 2nd, minor-3rd, 5th)
    with gentle amplitude envelopes per partial, slight detuning for warmth.
    Returns float32 (samples, 2).
    """
    n_samples = total_s * SAMPLE_RATE
    t = np.linspace(0, total_s, n_samples, endpoint=False)

    partials = [
        (1.000, 1.0,   0.0),     # root
        (2.003, 0.45,  0.3),     # octave, slight detune
        (2.997, 0.30, -0.2),     # 5th above octave
        (1.499, 0.25,  0.1),     # 5th
        (1.189, 0.15,  0.0),     # minor 3rd
    ]

    mix = np.zeros(n_samples, dtype=np.float64)
    for ratio, amp, pan_off in partials:
        freq = root_hz * ratio
        detune = 1.0 + random.uniform(-0.002, 0.002)
        mix += amp * np.sin(2 * np.pi * freq * detune * t)

    mix /= np.abs(mix).max() + 1e-9

    # Stereo: slight L/R detuning for width
    left  = mix + 0.12 * np.sin(2 * np.pi * root_hz * 1.001 * t)
    right = mix + 0.12 * np.sin(2 * np.pi * root_hz * 0.999 * t)
    stereo = np.stack([left, right], axis=1).astype(np.float32)

    # LPF to remove any harsh highs
    stereo = butter_lpf(stereo, 3000.0).astype(np.float32)

    # Normalise to -1..1
    peak = np.abs(stereo).max()
    if peak > 0:
        stereo /= peak

    # Tile with loop-period amplitude modulation (very slow swell, ~loop_s period)
    swell = 0.7 + 0.3 * np.sin(2 * np.pi * t / loop_s)
    stereo *= swell[:, None]

    return stereo


def apply_master_envelope(arr: np.ndarray, total_s: int,
                           fade_in_s: int, fade_out_s: int) -> np.ndarray:
    n = arr.shape[0]
    env = np.ones(n, dtype=np.float32)

    fade_in_n  = fade_in_s  * SAMPLE_RATE
    fade_out_n = fade_out_s * SAMPLE_RATE

    env[:fade_in_n]  = np.linspace(0.0, 1.0, fade_in_n)
    env[-fade_out_n:] = np.linspace(1.0, 0.0, fade_out_n)

    return arr * env[:, None]


# ── main ──────────────────────────────────────────────────────────────────────

def main(slug: str):
    print(f"\n[ENO] Species: {slug}")

    # ── 1. Bird seed ──────────────────────────────────────────────────────────
    seed_path = SEEDS_DIR / f"{slug}_seed.mp3"
    if not seed_path.exists():
        sys.exit(f"[ERR] Seed not found: {seed_path}")

    bird_raw = to_stereo_44k(AudioSegment.from_file(seed_path))
    bird_raw = bird_raw + BIRD_DB
    bird_loop_seg = make_loop(bird_raw, BIRD_LOOP_S, TOTAL_S)
    print(f"[OK]  Bird loop:    {BIRD_LOOP_S}s tile × {math.ceil(TOTAL_S/BIRD_LOOP_S)} = {len(bird_loop_seg)/1000:.1f}s")

    # ── 2. Melody stem (Suno file, diffuse / LPF'd) ──────────────────────────
    suno_path = find_suno(slug)
    if suno_path:
        print(f"[MATCHED] Suno: {suno_path.name}")
        suno_raw = to_stereo_44k(AudioSegment.from_file(suno_path))
        # Heavy LPF → dissolves the mix into a warm ambient wash
        suno_np  = seg_to_np(suno_raw).astype(np.float32)
        suno_np  = butter_lpf(suno_np, 800.0).astype(np.float32)    # only lows
        suno_np  = butter_hpf(suno_np, 60.0).astype(np.float32)     # no rumble
        suno_seg = np_to_seg(suno_np) + MELODY_DB
        mel_loop_seg = make_loop(suno_seg, MELODY_LOOP_S, TOTAL_S)
        print(f"[OK]  Melody loop:  {MELODY_LOOP_S}s tile × {math.ceil(TOTAL_S/MELODY_LOOP_S)} = {len(mel_loop_seg)/1000:.1f}s")
    else:
        print(f"[SKIP] No Suno file for {slug} — melody layer silent")
        mel_loop_seg = AudioSegment.silent(duration=TOTAL_S * 1000,
                                           frame_rate=SAMPLE_RATE)

    # ── 3. Synthesised string pad ─────────────────────────────────────────────
    pad_np   = make_pad_np(TOTAL_S, PAD_LOOP_S)
    pad_seg  = np_to_seg(pad_np) + PAD_DB
    print(f"[OK]  Pad loop:     {PAD_LOOP_S}s swell, synthesised")

    # ── 4. Mix all three ──────────────────────────────────────────────────────
    mix = bird_loop_seg.overlay(mel_loop_seg).overlay(pad_seg)
    print(f"[OK]  Mix duration: {len(mix)/1000:.1f}s")

    # ── 5. Master envelope ────────────────────────────────────────────────────
    mix_np  = seg_to_np(mix).astype(np.float32)
    mix_np  = apply_master_envelope(mix_np, TOTAL_S, FADE_IN_S, FADE_OUT_S)

    # Gentle master LPF + HPF
    mix_np = butter_lpf(mix_np, 12000.0).astype(np.float32)
    mix_np = butter_hpf(mix_np, 40.0).astype(np.float32)

    # Normalise to -6 dBFS
    peak = np.abs(mix_np).max()
    if peak > 0:
        target_peak = 10 ** (-6.0 / 20)
        mix_np = (mix_np / peak * target_peak).astype(np.float32)

    final = np_to_seg(mix_np)

    # ── 6. Export ─────────────────────────────────────────────────────────────
    out_path = OUT_DIR / f"{slug}_eno_method.mp3"
    final.export(str(out_path), format="mp3", bitrate="320k",
                 tags={"title": f"{slug} — Eno Method",
                       "comment": f"bird={BIRD_LOOP_S}s melody={MELODY_LOOP_S}s pad={PAD_LOOP_S}s"})
    mb = out_path.stat().st_size / 1_000_000
    print(f"[DONE] {out_path.name}  ({mb:.1f} MB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("slug", nargs="?", default="hermit_thrush",
                        help="Species slug (default: hermit_thrush)")
    args = parser.parse_args()
    main(args.slug)
