"""
mix_final.py — Mix Suno track with natural bird recording moments + spatial mastering.

Expected inputs:
  /output/suno/hermit_thrush_suno.mp3          ← Suno-generated track
  /output/hermit_thrush/hermit_thrush_best.mp3 ← original bird recording
    (falls back to data/midi_library/hermit_thrush/hermit_thrush_source.mp3)

Output:
  /output/final/hermit_thrush_naturetunes.mp3  (320 kbps)

Bird clips:
  Clip A (0–8 s)   → 0:05,     pan 30% left,  -14 dB, LPF 8 kHz
  Clip B (8–16 s)  → halfway,  pan 30% right, -14 dB, LPF 8 kHz
  Clip C (16–24 s) → -30 s,    center,        -14 dB, LPF 8 kHz
  Each: 2 s fade-in, 3 s fade-out

Final mix mastering:
  HPF 40 Hz  — remove sub-bass rumble
  Compression — 4:1 ratio, -18 dBFS threshold, 10 ms attack, 100 ms release
  Normalize to -6 dBFS
"""

from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt
from pydub import AudioSegment

ROOT      = Path(__file__).parent.parent
SUNO_DIR  = ROOT / "output" / "suno"
FINAL_DIR = ROOT / "output" / "final"

SAMPLE_RATE    = 44100
CHANNELS       = 2

CLIP_VOLUME_DB = -14
FADE_IN_MS     = 2_000
FADE_OUT_MS    = 3_000
LPF_HZ         = 8_000   # low-pass on bird clips
HPF_HZ         = 40      # high-pass on final mix
TARGET_DBFS    = -6      # final normalization

# Compressor settings
COMP_THRESHOLD_DB = -18.0
COMP_RATIO        = 4.0
COMP_ATTACK_MS    = 10
COMP_RELEASE_MS   = 100

CLIPS = [
    (0,  8,   -0.30),  # Clip A: 30% left
    (8,  16,   0.30),  # Clip B: 30% right
    (16, 24,   0.00),  # Clip C: center
]


# ── DSP helpers ───────────────────────────────────────────────────────────────

def seg_to_float(seg: AudioSegment) -> np.ndarray:
    """AudioSegment → float32 array shape (samples, channels)."""
    seg = seg.set_sample_width(2)
    raw = np.frombuffer(seg.raw_data, dtype=np.int16).astype(np.float32)
    return (raw / 32768.0).reshape(-1, seg.channels)


def float_to_seg(arr: np.ndarray, frame_rate: int, channels: int) -> AudioSegment:
    """float32 array → AudioSegment."""
    pcm = (np.clip(arr, -1.0, 1.0) * 32767).astype(np.int16)
    return AudioSegment(pcm.tobytes(), frame_rate=frame_rate,
                        sample_width=2, channels=channels)


def butter_filter(seg: AudioSegment, cutoff_hz: int, btype: str) -> AudioSegment:
    """Apply a 5th-order Butterworth filter (high or low pass)."""
    arr = seg_to_float(seg)
    nyq = seg.frame_rate / 2.0
    sos = butter(5, cutoff_hz / nyq, btype=btype, output="sos")
    filtered = sosfilt(sos, arr, axis=0)
    return float_to_seg(filtered, seg.frame_rate, seg.channels)


def compress(seg: AudioSegment,
             threshold_db: float = COMP_THRESHOLD_DB,
             ratio: float = COMP_RATIO,
             attack_ms: float = COMP_ATTACK_MS,
             release_ms: float = COMP_RELEASE_MS) -> AudioSegment:
    """
    Simple feed-forward RMS compressor.
    Operates per-sample with smoothed gain envelope.
    """
    arr = seg_to_float(seg)           # (samples, channels)
    rate = seg.frame_rate

    threshold_lin = 10 ** (threshold_db / 20.0)
    attack_coef   = np.exp(-1.0 / (rate * attack_ms  / 1000.0))
    release_coef  = np.exp(-1.0 / (rate * release_ms / 1000.0))

    # Mix down to mono for level detection
    mono = arr.mean(axis=1)

    gain_env = np.ones(len(mono), dtype=np.float32)
    gain = 1.0
    for i, sample in enumerate(mono):
        level = abs(sample)
        if level > threshold_lin:
            target_gain = threshold_lin + (level - threshold_lin) / ratio
            target_gain /= max(level, 1e-9)
        else:
            target_gain = 1.0
        coef = attack_coef if target_gain < gain else release_coef
        gain = coef * gain + (1.0 - coef) * target_gain
        gain_env[i] = gain

    compressed = arr * gain_env[:, np.newaxis]
    return float_to_seg(compressed, rate, seg.channels)


def normalize_to_dbfs(seg: AudioSegment, target_db: float = TARGET_DBFS) -> AudioSegment:
    if seg.dBFS == -float("inf"):
        return seg
    return seg.apply_gain(target_db - seg.dBFS)


# ── Audio loading / normalization ─────────────────────────────────────────────

def std(seg: AudioSegment) -> AudioSegment:
    return seg.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS)


# ── Bird clip construction ────────────────────────────────────────────────────

def make_clip(bird: AudioSegment, start_s: float, end_s: float, pan: float) -> AudioSegment:
    clip = bird[int(start_s * 1000) : int(end_s * 1000)]
    clip = clip.apply_gain(CLIP_VOLUME_DB)
    clip = butter_filter(clip, LPF_HZ, "low")
    clip = clip.pan(pan)                              # pydub: -1.0 left … +1.0 right
    clip = clip.fade_in(min(FADE_IN_MS,  len(clip) // 2))
    clip = clip.fade_out(min(FADE_OUT_MS, len(clip) // 2))
    return clip


def overlay_at(base: AudioSegment, clip: AudioSegment, position_ms: int) -> AudioSegment:
    needed = position_ms + len(clip)
    if needed > len(base):
        base = base + AudioSegment.silent(duration=needed - len(base),
                                          frame_rate=SAMPLE_RATE)
    return base.overlay(clip, position=position_ms)


# ── File finders ──────────────────────────────────────────────────────────────

def find_bird_recording(species: str) -> Path:
    candidates = [
        ROOT / "output" / species / f"{species}_best.mp3",
        ROOT / "data" / "midi_library" / species / f"{species}_source.mp3",
        ROOT / "data" / "midi_library" / species / f"{species}_best.mp3",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"No bird recording found for '{species}'. Tried:\n" +
        "\n".join(f"  {p}" for p in candidates)
    )


def find_suno(species: str) -> Path:
    exact = SUNO_DIR / f"{species}_suno.mp3"
    if exact.exists():
        return exact
    words = [w for w in species.split("_") if len(w) > 2]
    for f in sorted(SUNO_DIR.glob("*.mp3")):
        slug = f.stem.lower().replace(" ", "_").replace("-", "_")
        if all(w in slug for w in words):
            return f
    raise FileNotFoundError(
        f"No suno file found for '{species}' in {SUNO_DIR}.\n"
        f"Expected: {exact.name} or a file containing {words}"
    )


# ── Main pipeline ─────────────────────────────────────────────────────────────

def mix(species: str) -> None:
    suno_path = find_suno(species)
    bird_path = find_bird_recording(species)

    print(f"  loading suno: {suno_path.name}")
    suno = std(AudioSegment.from_file(str(suno_path)))
    print(f"  loading bird: {bird_path.name}")
    bird = std(AudioSegment.from_file(str(bird_path)))

    total_ms = len(suno)
    half_ms  = total_ms // 2

    positions = [
        5_000,                          # Clip A at 0:05
        half_ms,                        # Clip B at halfway
        max(0, total_ms - 30_000),      # Clip C at 30 s before end
    ]

    labels = ["A (L)", "B (R)", "C (C)"]
    print(f"\n  assembling clips over {total_ms/1000:.1f}s suno track...")

    result = suno
    for (start_s, end_s, pan), pos_ms, label in zip(CLIPS, positions, labels):
        clip = make_clip(bird, start_s, end_s, pan)
        result = overlay_at(result, clip, pos_ms)
        ts = f"{pos_ms//60000}:{(pos_ms//1000)%60:02d}"
        print(f"    clip {label}: bird {start_s}–{end_s}s → placed @{ts}  pan={pan:+.0%}")

    print("\n  mastering...")
    print("    HPF 40 Hz")
    result = butter_filter(result, HPF_HZ, "high")

    print("    compression (4:1, threshold -18 dBFS)")
    result = compress(result)

    print(f"    normalize → {TARGET_DBFS} dBFS  (was {result.dBFS:.1f} dBFS)")
    result = normalize_to_dbfs(result, TARGET_DBFS)

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FINAL_DIR / f"{species}_naturetunes.mp3"
    result.export(str(out_path), format="mp3", bitrate="320k")

    print(f"\n[OK] {species} → output/final/{out_path.name}  "
          f"({out_path.stat().st_size / 1024**2:.1f} MB, 320 kbps)")


def main() -> None:
    mix("hermit_thrush")


if __name__ == "__main__":
    main()
