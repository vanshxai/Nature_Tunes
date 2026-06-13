"""
midi_library.py — build a clean MIDI sample library from BirdMind recordings.

Converts the single best (lowest silence_ratio) recording per species to MIDI
using basic_pitch, then organises audio + MIDI side-by-side in data/midi_library/.

Usage:
  python src/midi_library.py
"""

import logging
import re
import shutil
import sys
from pathlib import Path

# Silence basic_pitch and tensorflow noise before importing them
logging.getLogger("basic_pitch").setLevel(logging.ERROR)
logging.getLogger("tensorflow").setLevel(logging.ERROR)
logging.getLogger("absl").setLevel(logging.ERROR)

import contextlib
import io
import os

import mido
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
METADATA_CSV = ROOT / "data" / "prototype" / "prototype_metadata.csv"
OUT_DIR = ROOT / "data" / "midi_library"
INDEX_CSV = OUT_DIR / "library_index.csv"
ERROR_LOG = OUT_DIR / "errors.log"


@contextlib.contextmanager
def suppress_stdout():
    """Redirect stdout to /dev/null to silence basic_pitch's print() calls."""
    with open(os.devnull, "w") as devnull:
        old = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old


# ── helpers ───────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    return re.sub(r"[^\w]+", "_", name.lower()).strip("_")


def count_midi_notes(midi_path: Path) -> int:
    mid = mido.MidiFile(str(midi_path))
    return sum(
        1 for track in mid.tracks
        for msg in track
        if msg.type == "note_on" and msg.velocity > 0
    )


def log_error(msg: str) -> None:
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ERROR_LOG, "a") as f:
        f.write(msg + "\n")
    print(f"  [error] {msg}")


# ── conversion ────────────────────────────────────────────────────────────────

def convert_with_basic_pitch(audio_path: Path, midi_out: Path) -> int:
    """Run basic_pitch on audio_path, save MIDI to midi_out. Returns note count."""
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH

    with suppress_stdout():
        _, midi_data, _ = predict(
            str(audio_path),
            ICASSP_2022_MODEL_PATH,
        )

    midi_out.parent.mkdir(parents=True, exist_ok=True)
    midi_data.write(str(midi_out))

    return count_midi_notes(midi_out)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if ERROR_LOG.exists():
        ERROR_LOG.unlink()

    # ── Step 1: pick best file per species ────────────────────────────────────
    df = pd.read_csv(METADATA_CSV)
    df = df[df["usable"] == True].copy()
    # Sort so that within each species, lowest silence wins; longest duration breaks ties
    df_sorted = df.sort_values(["common_name", "silence_ratio", "duration"],
                               ascending=[True, True, False])
    best = df_sorted.groupby("common_name", sort=False).first().reset_index()
    best = best.sort_values("common_name").reset_index(drop=True)

    total = len(best)
    print(f"Found {total} species — converting best recording each...\n")

    index_rows = []
    results = []   # (common_name, xc_id, duration, notes) for report

    # ── Step 2 & 3: convert + copy ────────────────────────────────────────────
    for i, row in best.iterrows():
        common_name = row["common_name"]
        xc_id = int(row["xc_id"])
        slug = slugify(common_name)
        audio_path = ROOT / row["file_path"]

        print(f"  Converting {i + 1}/{total}: {common_name}...", end=" ", flush=True)

        species_dir = OUT_DIR / slug
        species_dir.mkdir(parents=True, exist_ok=True)

        midi_out = species_dir / f"{slug}_sample.mid"
        mp3_out = species_dir / f"{slug}_source.mp3"

        notes_in_midi = 0

        if not audio_path.exists():
            msg = f"{common_name} | XC{xc_id} | missing audio: {audio_path}"
            log_error(msg)
            print("missing audio")
        else:
            try:
                # Copy source MP3
                shutil.copy2(audio_path, mp3_out)

                # Convert to MIDI
                notes_in_midi = convert_with_basic_pitch(audio_path, midi_out)
                print(f"{notes_in_midi} notes")
            except Exception as exc:
                msg = f"{common_name} | XC{xc_id} | {exc}"
                log_error(msg)
                print(f"failed: {exc}")

        results.append((common_name, xc_id, int(row["duration"]), notes_in_midi))

        index_rows.append({
            "species":          slug,
            "common_name":      common_name,
            "source_xc_id":     xc_id,
            "source_file":      str(audio_path.relative_to(ROOT)),
            "midi_file":        str(midi_out.relative_to(ROOT)) if midi_out.exists() else "",
            "duration_seconds": int(row["duration"]),
            "silence_ratio":    round(float(row["silence_ratio"]), 6),
            "onset_density":    round(float(row["onset_density"]), 4) if pd.notna(row.get("onset_density")) else None,
            "dominant_freq_hz": round(float(row["dominant_freq_hz"]), 2) if pd.notna(row.get("dominant_freq_hz")) else None,
            "notes_in_midi":    notes_in_midi,
        })

    # ── Step 4: save index ────────────────────────────────────────────────────
    index_df = pd.DataFrame(index_rows)
    index_df.to_csv(INDEX_CSV, index=False)

    # ── Step 5: completion report ─────────────────────────────────────────────
    successful = [(n, xc, dur, notes) for (n, xc, dur, notes) in results if notes > 0]
    total_notes = sum(r[3] for r in results)
    converted = sum(1 for r in results if r[3] > 0)

    print()
    print("=" * 30)
    print("BirdMind MIDI Sample Library")
    print("=" * 30)
    print(f"Species converted : {converted}/{total}")
    print(f"Total MIDI notes  : {total_notes}")
    print(f"Output directory  : data/midi_library/")
    print()
    print("Per species:")
    for name, xc_id, duration, notes in results:
        print(f"  {name:<26} → {notes:>5} notes  (XC#{xc_id}, {duration}s)")

    if successful:
        min_row = min(successful, key=lambda r: r[3])
        max_row = max(successful, key=lambda r: r[3])
        print()
        print(f"Lowest note count  : {min_row[0]} ({min_row[3]} notes)")
        print(f"Highest note count : {max_row[0]} ({max_row[3]} notes)")
    print("=" * 30)


if __name__ == "__main__":
    main()
