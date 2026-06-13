"""
bird_to_midi.py — convert BirdMind audio recordings to MIDI.

Usage:
  python src/bird_to_midi.py --file <path>    --method pyin|basic_pitch [--quantize]
  python src/bird_to_midi.py --species <name> --method pyin|basic_pitch [--quantize]
  python src/bird_to_midi.py --all            --method pyin|basic_pitch [--quantize]
"""

import argparse
import logging
import os
import re
import sys
import warnings
from math import log2
from pathlib import Path

import librosa
import mido
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.getLogger().setLevel(logging.ERROR)

# ── constants ─────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
METADATA_CSV = ROOT / "data" / "prototype" / "prototype_metadata.csv"
MIDI_DIR = ROOT / "data" / "midi"

SR = 22050
TICKS_PER_BEAT = 480
TEMPO_US = 500_000  # 120 BPM
BPM = 120.0

MIDI_C2 = 36
MIDI_C8 = 108
VOICED_PROB_THRESHOLD = 0.6
MIN_NOTE_DURATION_S = 0.05   # 50 ms
MERGE_GAP_S = 0.03           # 30 ms
SEMITONE_TOLERANCE = 0.5     # frames within ±0.5 st = same note

SIXTEENTH_S = 60.0 / BPM / 4  # duration of a 1/16th note in seconds


# ── helpers ───────────────────────────────────────────────────────────────────

def hz_to_midi(f0: float) -> float:
    return 69 + 12 * log2(f0 / 440.0)


def midi_to_note_name(midi: int) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = (midi // 12) - 1
    return f"{names[midi % 12]}{octave}"


def seconds_to_ticks(seconds: float) -> int:
    return max(0, round(seconds * TICKS_PER_BEAT * (BPM / 60.0)))


def rms_to_velocity(rms: float, rms_max: float) -> int:
    if rms_max < 1e-9:
        return 64
    v = int(round(1 + 126 * (rms / rms_max)))
    return max(1, min(127, v))


def quantize_onset(onset_s: float) -> float:
    grid_idx = round(onset_s / SIXTEENTH_S)
    return grid_idx * SIXTEENTH_S


# ── post-processing ────────────────────────────────────────────────────────────

def postprocess_notes(notes: list[dict], do_quantize: bool) -> list[dict]:
    """
    notes: list of dicts with keys onset_s, duration_s, midi_note, velocity
    Returns filtered, optionally quantized, and merged list.
    """
    # 1. Remove too short
    notes = [n for n in notes if n["duration_s"] >= MIN_NOTE_DURATION_S]

    # 2. Remove out-of-range MIDI notes
    notes = [n for n in notes if MIDI_C2 <= n["midi_note"] <= MIDI_C8]

    # 3. Quantize onsets to nearest 1/16th
    if do_quantize:
        for n in notes:
            n["onset_s"] = quantize_onset(n["onset_s"])

    # 4. Sort by onset
    notes.sort(key=lambda n: n["onset_s"])

    # 5. Merge consecutive identical notes with gap < MERGE_GAP_S
    merged = []
    for n in notes:
        if (merged
                and merged[-1]["midi_note"] == n["midi_note"]
                and (n["onset_s"] - (merged[-1]["onset_s"] + merged[-1]["duration_s"])) < MERGE_GAP_S):
            merged[-1]["duration_s"] += (
                n["onset_s"] - merged[-1]["onset_s"] - merged[-1]["duration_s"]
            ) + n["duration_s"]
            merged[-1]["velocity"] = max(merged[-1]["velocity"], n["velocity"])
        else:
            merged.append(dict(n))

    return merged


# ── MIDI assembly ──────────────────────────────────────────────────────────────

def notes_to_midi_file(notes: list[dict], species_name: str, out_path: Path) -> None:
    mid = mido.MidiFile(type=0, ticks_per_beat=TICKS_PER_BEAT)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    track.append(mido.MetaMessage("set_tempo", tempo=TEMPO_US, time=0))
    track.append(mido.MetaMessage("track_name", name=species_name, time=0))

    # Build absolute-tick event list, then convert to delta ticks
    events = []
    for n in notes:
        on_tick = seconds_to_ticks(n["onset_s"])
        off_tick = seconds_to_ticks(n["onset_s"] + n["duration_s"])
        events.append((on_tick,  "note_on",  n["midi_note"], n["velocity"]))
        events.append((off_tick, "note_off", n["midi_note"], 0))

    events.sort(key=lambda e: (e[0], 0 if e[1] == "note_off" else 1))

    prev_tick = 0
    for abs_tick, msg_type, note, vel in events:
        delta = abs_tick - prev_tick
        if msg_type == "note_on":
            track.append(mido.Message("note_on", channel=0, note=note,
                                      velocity=vel, time=delta))
        else:
            track.append(mido.Message("note_off", channel=0, note=note,
                                      velocity=0, time=delta))
        prev_tick = abs_tick

    out_path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(str(out_path))


# ── METHOD 1: PYIN ────────────────────────────────────────────────────────────

def convert_pyin(audio_path: Path, do_quantize: bool) -> list[dict]:
    y, _ = librosa.load(str(audio_path), sr=SR, mono=True)

    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C8"),
        frame_length=2048,
        sr=SR,
    )

    hop_length = 512  # pyin default
    frame_times = librosa.frames_to_time(
        np.arange(len(f0)), sr=SR, hop_length=hop_length
    )

    # RMS per frame for velocity estimation
    rms_frames = librosa.feature.rms(
        y=y, frame_length=2048, hop_length=hop_length
    )[0]
    # Pad/trim rms to match f0 length
    rms_frames = np.pad(rms_frames, (0, max(0, len(f0) - len(rms_frames))))[:len(f0)]
    rms_max = rms_frames.max()

    # Segment into notes: consecutive frames with same MIDI note (±0.5 st)
    notes = []
    i = 0
    while i < len(f0):
        # Skip unvoiced / low-confidence frames
        if (not voiced_flag[i]
                or voiced_prob[i] < VOICED_PROB_THRESHOLD
                or f0[i] is None
                or np.isnan(f0[i])):
            i += 1
            continue

        midi_f = hz_to_midi(f0[i])
        midi_note = round(midi_f)
        onset_i = i

        # Extend while same note (within tolerance)
        seg_rms = [rms_frames[i]]
        i += 1
        while i < len(f0):
            if (not voiced_flag[i]
                    or voiced_prob[i] < VOICED_PROB_THRESHOLD
                    or f0[i] is None
                    or np.isnan(f0[i])):
                break
            candidate = hz_to_midi(f0[i])
            if abs(candidate - midi_f) > SEMITONE_TOLERANCE:
                break
            seg_rms.append(rms_frames[i])
            i += 1

        onset_s = float(frame_times[onset_i])
        end_s = float(frame_times[i - 1]) + hop_length / SR
        duration_s = end_s - onset_s
        velocity = rms_to_velocity(float(np.mean(seg_rms)), rms_max)

        notes.append({
            "onset_s": onset_s,
            "duration_s": duration_s,
            "midi_note": midi_note,
            "velocity": velocity,
        })

    return postprocess_notes(notes, do_quantize)


# ── METHOD 2: BASIC PITCH ─────────────────────────────────────────────────────

def convert_basic_pitch(audio_path: Path, do_quantize: bool) -> list[dict]:
    # Import here so missing basic-pitch doesn't crash pyin usage
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH

    model_output, midi_data, note_events = predict(
        str(audio_path),
        ICASSP_2022_MODEL_PATH,
    )

    # note_events: list of (start_time_s, end_time_s, pitch_midi, amplitude, [bends])
    notes = []
    for event in note_events:
        start_s, end_s, pitch, amplitude = event[:4]
        duration_s = float(end_s) - float(start_s)
        velocity = max(1, min(127, int(round(float(amplitude) * 127))))
        notes.append({
            "onset_s": float(start_s),
            "duration_s": duration_s,
            "midi_note": int(pitch),
            "velocity": velocity,
        })

    return postprocess_notes(notes, do_quantize)


# ── print summary ─────────────────────────────────────────────────────────────

def print_summary(common_name: str, file_path: Path, method: str,
                  notes: list[dict], audio_duration: float, out_path: Path) -> None:
    if not notes:
        print(f"  [!] No notes detected in {file_path.name}")
        return

    midi_notes = [n["midi_note"] for n in notes]
    velocities = [n["velocity"] for n in notes]
    lo, hi = min(midi_notes), max(midi_notes)
    avg_vel = int(round(np.mean(velocities)))

    print(
        f"\n  Species      : {common_name}\n"
        f"  File         : {file_path.name}\n"
        f"  Method       : {method}\n"
        f"  Notes found  : {len(notes)}\n"
        f"  Duration     : {audio_duration:.1f}s\n"
        f"  Pitch range  : {midi_to_note_name(lo)} - {midi_to_note_name(hi)} "
        f"(MIDI {lo}-{hi})\n"
        f"  Avg velocity : {avg_vel}\n"
        f"  Output       : {out_path.relative_to(ROOT)}"
    )


# ── core per-file entry point ─────────────────────────────────────────────────

def process_file(audio_path: Path, common_name: str, xc_id: str,
                 method: str, do_quantize: bool) -> None:
    species_slug = re.sub(r"[^\w]+", "_", common_name.lower()).strip("_")
    out_path = MIDI_DIR / species_slug / f"{xc_id}_{method}.mid"

    if out_path.exists():
        print(f"  [skip] {out_path.relative_to(ROOT)} already exists")
        return

    try:
        y, _ = librosa.load(str(audio_path), sr=SR, mono=True)
        audio_duration = len(y) / SR

        if method == "pyin":
            notes = convert_pyin(audio_path, do_quantize)
        else:
            notes = convert_basic_pitch(audio_path, do_quantize)

        if notes:
            notes_to_midi_file(notes, common_name, out_path)

        print_summary(common_name, audio_path, method, notes, audio_duration, out_path)

    except Exception as exc:
        print(f"  [error] {audio_path.name}: {exc}")


# ── dataset helpers ───────────────────────────────────────────────────────────

def load_metadata() -> pd.DataFrame:
    df = pd.read_csv(METADATA_CSV)
    df = df[df["usable"] == True].copy()
    return df


def slug_to_common_name(slug: str, df: pd.DataFrame) -> str | None:
    slug_norm = slug.lower().replace("-", " ").replace("_", " ")
    for name in df["common_name"].unique():
        if name.lower() == slug_norm:
            return name
    return None


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Convert BirdMind audio to MIDI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=Path, help="Single audio file path")
    group.add_argument("--species", type=str, help="Species common name or slug")
    group.add_argument("--all", action="store_true", help="Entire usable dataset")

    parser.add_argument(
        "--method", choices=["pyin", "basic_pitch"], required=True,
        help="Transcription method"
    )
    parser.add_argument(
        "--quantize", action="store_true",
        help="Snap note onsets to nearest 1/16th note grid"
    )
    args = parser.parse_args()

    # ── single file mode ──────────────────────────────────────────────────────
    if args.file:
        audio_path = Path(args.file)
        if not audio_path.exists():
            sys.exit(f"File not found: {audio_path}")

        # Try to find species info from CSV
        xc_id = audio_path.stem  # e.g. XC103068
        common_name = "Unknown"
        try:
            df = load_metadata()
            row = df[df["xc_id"].astype(str) == xc_id.replace("XC", "")]
            if not row.empty:
                common_name = row.iloc[0]["common_name"]
        except Exception:
            pass

        process_file(audio_path, common_name, xc_id, args.method, args.quantize)
        return

    # ── species / all mode ────────────────────────────────────────────────────
    df = load_metadata()

    if args.species:
        common_name = slug_to_common_name(args.species, df)
        if common_name is None:
            available = sorted(df["common_name"].unique())
            sys.exit(
                f"Species '{args.species}' not found.\nAvailable:\n  "
                + "\n  ".join(available)
            )
        rows = df[df["common_name"] == common_name]
        print(f"\n[{args.method.upper()}] {common_name} — {len(rows)} files")
    else:
        rows = df
        print(f"\n[{args.method.upper()}] Full dataset — {len(rows)} files")

    for _, row in rows.iterrows():
        audio_path = ROOT / row["file_path"]
        if not audio_path.exists():
            print(f"  [missing] {row['file_path']}")
            continue
        xc_id = f"XC{row['xc_id']}"
        process_file(audio_path, row["common_name"], xc_id, args.method, args.quantize)

    print(f"\nDone. MIDI files saved under data/midi/")


if __name__ == "__main__":
    main()
