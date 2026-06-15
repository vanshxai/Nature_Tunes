"""
extract_seed.py — Extract a clean 4–6 s bird-sound seed clip per species.

For each species in data/midi_library/:
  1. Load <slug>_source.mp3
  2. Skip leading silence (threshold -40 dBFS, min-silence 100 ms)
  3. Extract the first 4–6 s of actual bird sound from that point
  4. Apply high-pass filter at 1000 Hz (removes wind/rumble)
  5. Apply noise gate — silence anything below -35 dBFS per chunk
  6. Normalize to -3 dBFS
  7. Export to output/seeds/<slug>_seed.mp3

Usage:
  python src/extract_seed.py
"""

from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt
from pydub import AudioSegment
from pydub.silence import detect_leading_silence

LIBRARY  = Path(__file__).parent.parent / "data" / "midi_library"
OUT_DIR  = Path(__file__).parent.parent / "output" / "seeds"

SILENCE_THRESH   = -40   # dBFS — leading silence detection threshold
MIN_SILENCE_MS   = 100   # ms chunk size for leading silence scan
TARGET_DBFS      = -3    # final normalization target
CLIP_MIN_MS      = 4_000
CLIP_MAX_MS      = 6_000

HPF_HZ           = 1000  # high-pass cutoff — removes wind/rumble below 1 kHz
HPF_ORDER        = 5     # Butterworth filter order

GATE_THRESH_DB   = -35   # noise gate: chunks quieter than this → silence
GATE_CHUNK_MS    = 20    # gate operates on 20 ms frames


def _seg_to_float(seg: AudioSegment) -> tuple[np.ndarray, int]:
    """Convert AudioSegment to float32 numpy array, shape (samples, channels)."""
    seg = seg.set_sample_width(2)  # ensure 16-bit
    raw = np.frombuffer(seg.raw_data, dtype=np.int16).astype(np.float32)
    raw /= 32768.0
    ch = seg.channels
    return raw.reshape(-1, ch), seg.frame_rate


def _float_to_seg(arr: np.ndarray, frame_rate: int, channels: int) -> AudioSegment:
    """Convert float32 numpy array back to AudioSegment."""
    clipped = np.clip(arr, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)
    return AudioSegment(
        pcm.tobytes(),
        frame_rate=frame_rate,
        sample_width=2,
        channels=channels,
    )


def apply_highpass(seg: AudioSegment, cutoff_hz: int = HPF_HZ) -> AudioSegment:
    """Butterworth high-pass filter via scipy."""
    samples, rate = _seg_to_float(seg)
    nyq = rate / 2.0
    sos = butter(HPF_ORDER, cutoff_hz / nyq, btype="high", output="sos")
    filtered = sosfilt(sos, samples, axis=0)
    return _float_to_seg(filtered, rate, seg.channels)


def apply_noise_gate(seg: AudioSegment,
                     threshold_db: float = GATE_THRESH_DB,
                     chunk_ms: int = GATE_CHUNK_MS) -> AudioSegment:
    """
    Simple chunk-level noise gate: any chunk whose dBFS is below
    threshold_db is replaced with silence.
    """
    chunks = [seg[i : i + chunk_ms] for i in range(0, len(seg), chunk_ms)]
    gated  = []
    for chunk in chunks:
        if len(chunk) == 0:
            continue
        if chunk.dBFS < threshold_db:
            gated.append(AudioSegment.silent(duration=len(chunk),
                                             frame_rate=seg.frame_rate))
        else:
            gated.append(chunk)
    return sum(gated, AudioSegment.empty())


def extract_seed(slug: str, src_path: Path, out_path: Path) -> str:
    audio = AudioSegment.from_file(str(src_path))

    # 1. Skip leading silence
    start_ms = detect_leading_silence(audio, silence_threshold=SILENCE_THRESH,
                                      chunk_size=MIN_SILENCE_MS)

    # 2. Extract 4–6 s of actual bird sound
    end_ms = min(start_ms + CLIP_MAX_MS, len(audio))
    clip   = audio[start_ms:end_ms]

    if len(clip) < CLIP_MIN_MS:
        clip = clip + AudioSegment.silent(duration=CLIP_MIN_MS - len(clip))

    # 3. High-pass filter at 1000 Hz — remove wind/rumble
    clip = apply_highpass(clip, HPF_HZ)

    # 4. Noise gate — silence chunks below -35 dBFS
    clip = apply_noise_gate(clip, GATE_THRESH_DB, GATE_CHUNK_MS)

    # 5. Normalize to -3 dBFS
    if clip.dBFS > -float("inf"):
        clip = clip.apply_gain(TARGET_DBFS - clip.dBFS)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    clip.export(str(out_path), format="mp3", bitrate="192k")

    duration = len(clip) / 1000
    return f"  ✓ {slug:<30} start={start_ms/1000:.2f}s  clip={duration:.1f}s  peak={clip.dBFS:.1f}dBFS"


def main():
    species_dirs = sorted(d for d in LIBRARY.iterdir() if d.is_dir())
    print(f"\nextract_seed — {len(species_dirs)} species → output/seeds/\n")

    ok = 0
    for sp_dir in species_dirs:
        slug = sp_dir.name
        src  = sp_dir / f"{slug}_source.mp3"
        out  = OUT_DIR / f"{slug}_seed.mp3"

        if not src.exists():
            print(f"  ✗ {slug:<30} no source MP3 found")
            continue

        try:
            msg = extract_seed(slug, src, out)
            print(msg)
            ok += 1
        except Exception as exc:
            print(f"  ✗ {slug:<30} {exc}")

    print(f"\n  Done: {ok}/{len(species_dirs)} seeds → output/seeds/\n")


if __name__ == "__main__":
    main()
