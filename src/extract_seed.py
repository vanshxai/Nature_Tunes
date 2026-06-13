"""
extract_seed.py — Extract a clean 4–6 s bird-sound seed clip per species.

For each species in data/midi_library/:
  1. Load <slug>_source.mp3
  2. Skip leading silence (threshold -40 dBFS, min-silence 100 ms)
  3. Extract the first 4–6 s of actual bird sound from that point
  4. Normalize to -3 dBFS
  5. Export to output/seeds/<slug>_seed.mp3

Usage:
  python src/extract_seed.py
"""

from pathlib import Path

from pydub import AudioSegment
from pydub.silence import detect_leading_silence

LIBRARY  = Path(__file__).parent.parent / "data" / "midi_library"
OUT_DIR  = Path(__file__).parent.parent / "output" / "seeds"

SILENCE_THRESH   = -40   # dBFS — anything below this is "silence"
MIN_SILENCE_MS   = 100   # ms of sustained silence to count as leading silence
TARGET_DBFS      = -3    # normalize to this level
CLIP_MIN_MS      = 4_000 # 4 s minimum clip
CLIP_MAX_MS      = 6_000 # 6 s maximum clip


def extract_seed(slug: str, src_path: Path, out_path: Path) -> str:
    audio = AudioSegment.from_file(str(src_path))

    # Detect how many ms of leading silence to skip
    start_ms = detect_leading_silence(audio, silence_threshold=SILENCE_THRESH,
                                      chunk_size=MIN_SILENCE_MS)

    # Clip 4–6 s from where sound starts
    end_ms = min(start_ms + CLIP_MAX_MS, len(audio))
    clip   = audio[start_ms:end_ms]

    # Pad with silence if the recording is shorter than 4 s after the start
    if len(clip) < CLIP_MIN_MS:
        clip = clip + AudioSegment.silent(duration=CLIP_MIN_MS - len(clip))

    # Normalize to -3 dBFS
    gain_needed = TARGET_DBFS - clip.dBFS
    clip = clip.apply_gain(gain_needed)

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
