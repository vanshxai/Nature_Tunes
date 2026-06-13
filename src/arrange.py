"""
arrange.py — NatureTunes composition pipeline.

For each species:
  1. Read bird MIDI from midi_library
  2. Add flute (GM 73), string pad (GM 48), and percussion tracks
  3. Save combined MIDI
  4. Render to WAV via fluidsynth CLI
  5. Convert WAV → MP3 via pydub
  6. Mix with original MP3 (bird -12 dB underneath)
  7. Save final MP3 to output/arranged/

Usage:
  python src/arrange.py --species all
  python src/arrange.py --species hermit_thrush
  python src/arrange.py --species hermit_thrush --sf2 /path/to/custom.sf2
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pretty_midi
from pydub import AudioSegment

# ── paths ─────────────────────────────────────────────────────────────────────

ROOT       = Path(__file__).parent.parent
LIBRARY    = ROOT / "data" / "midi_library"
OUT_DIR    = ROOT / "output" / "arranged"
ERROR_LOG  = OUT_DIR / "errors.log"

DEFAULT_SF2 = ROOT / "assets" / "soundfonts" / "vintage_dreams.sf2"

# FluidSynth binary — prefer Homebrew install
FLUIDSYNTH = shutil.which("fluidsynth") or "/usr/local/bin/fluidsynth"

# Naming patterns to try when scanning a species folder
MID_SUFFIXES = ["_sample.mid", "_best.mid", ".mid"]
MP3_SUFFIXES = ["_source.mp3", "_best.mp3", ".mp3"]

# ── MIDI constants ─────────────────────────────────────────────────────────────

GM_FLUTE      = 73   # GM program number (1-indexed)
GM_STRING_PAD = 48


# ── helpers ───────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    return re.sub(r"[^\w]+", "_", name.lower()).strip("_")


def find_file(folder: Path, suffixes: list[str]) -> Path | None:
    for suf in suffixes:
        candidates = list(folder.glob(f"*{suf}"))
        if candidates:
            return candidates[0]
    return None


def log_error(msg: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(ERROR_LOG, "a") as f:
        f.write(msg + "\n")


def note_name_to_num(name: str) -> int:
    """pretty_midi helper wrapper."""
    return pretty_midi.note_name_to_number(name)


# ── MIDI arrangement ──────────────────────────────────────────────────────────

def build_arranged_midi(bird_mid_path: Path) -> pretty_midi.PrettyMIDI:
    pm = pretty_midi.PrettyMIDI(str(bird_mid_path))

    # Gather all notes from existing instruments as the "melody"
    melody_notes = []
    for inst in pm.instruments:
        if not inst.is_drum:
            melody_notes.extend(inst.notes)
    melody_notes.sort(key=lambda n: n.start)

    song_end = pm.get_end_time() if melody_notes else 30.0

    # ── Track 1: Flute (GM 73) ─────────────────────────────────────────────
    # Duplicate melody, transpose down one octave (12 semitones)
    flute = pretty_midi.Instrument(program=GM_FLUTE - 1, name="Flute")
    for n in melody_notes:
        pitched = max(0, min(127, n.pitch - 12))
        flute.notes.append(pretty_midi.Note(
            velocity=max(1, min(127, int(n.velocity * 0.85))),
            pitch=pitched,
            start=n.start,
            end=n.end,
        ))

    # ── Track 2: String Pad (GM 48) ────────────────────────────────────────
    # Every 4th note, held for 2.0s, reduced velocity for slow-attack feel
    pad = pretty_midi.Instrument(program=GM_STRING_PAD - 1, name="String Pad")
    for idx, n in enumerate(melody_notes):
        if idx % 4 == 0:
            pad.notes.append(pretty_midi.Note(
                velocity=max(1, min(127, int(n.velocity * 0.6))),
                pitch=max(0, min(127, n.pitch - 5)),   # down a perfect 4th
                start=n.start,
                end=n.start + 2.0,
            ))

    pm.instruments.extend([flute, pad])
    return pm


# ── audio rendering ───────────────────────────────────────────────────────────

def render_midi_to_wav(mid_path: Path, wav_path: Path, sf2_path: Path) -> None:
    """Call fluidsynth CLI: fluidsynth -ni -F out.wav soundfont.sf2 input.mid"""
    result = subprocess.run(
        [FLUIDSYNTH, "-ni", "-g", "0.7", "-F", str(wav_path), "-r", "44100",
         str(sf2_path), str(mid_path)],
        capture_output=True, text=True, timeout=300,
    )
    if not wav_path.exists() or wav_path.stat().st_size < 1000:
        raise RuntimeError(
            f"fluidsynth render failed: {result.stderr[:300]}"
        )


def wav_to_mp3(wav_path: Path, mp3_path: Path, bitrate: str = "192k") -> None:
    seg = AudioSegment.from_wav(str(wav_path))
    seg.export(str(mp3_path), format="mp3", bitrate=bitrate)


def load_audio(path: Path) -> AudioSegment:
    """Load audio file regardless of whether it's actually WAV or MP3."""
    try:
        return AudioSegment.from_file(str(path))
    except Exception:
        return AudioSegment.from_mp3(str(path))


def mix_with_bird(composed_mp3: Path, bird_mp3: Path, out_path: Path) -> None:
    """
    Lay the original bird recording -12 dB underneath the composed track.
    Loops bird MP3 if it's shorter than the composition.
    """
    composed = AudioSegment.from_mp3(str(composed_mp3))
    bird_raw = load_audio(bird_mp3) - 12   # -12 dB

    bird_raw = bird_raw.set_frame_rate(44100).set_channels(2)
    composed = composed.set_frame_rate(44100).set_channels(2)

    # Loop bird audio to match composition length
    if len(bird_raw) < len(composed):
        repeats = (len(composed) // len(bird_raw)) + 1
        bird_raw = bird_raw * repeats
    bird_trimmed = bird_raw[:len(composed)]

    mixed = composed.overlay(bird_trimmed)
    mixed.export(str(out_path), format="mp3", bitrate="192k")


# ── per-species pipeline ──────────────────────────────────────────────────────

def process_species(species_dir: Path, sf2_path: Path) -> tuple[bool, str]:
    """
    Returns (success, message).
    """
    slug = species_dir.name
    mid_path = find_file(species_dir, MID_SUFFIXES)
    mp3_path = find_file(species_dir, MP3_SUFFIXES)

    if mid_path is None:
        return False, f"[SKIP] {slug} — no MIDI file found"
    if mp3_path is None:
        return False, f"[SKIP] {slug} — no MP3 file found"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    arranged_mid = OUT_DIR / f"{slug}_arranged.mid"
    final_mp3    = OUT_DIR / f"{slug}_final.mp3"

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            arranged_wav = tmp_path / "arranged.wav"
            composed_mp3 = tmp_path / "composed.mp3"

            # 1. Build MIDI arrangement
            arranged_pm = build_arranged_midi(mid_path)
            arranged_pm.write(str(arranged_mid))

            # 2. Render MIDI → WAV
            render_midi_to_wav(arranged_mid, arranged_wav, sf2_path)

            # 3. WAV → MP3
            wav_to_mp3(arranged_wav, composed_mp3)

            # 4. Mix with original bird MP3 at -12 dB
            mix_with_bird(composed_mp3, mp3_path, final_mp3)

        return True, f"[OK] {slug} → output/arranged/{slug}_final.mp3"

    except Exception as exc:
        msg = f"[ERR] {slug} — {exc}"
        log_error(msg)
        return False, msg


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="NatureTunes arrangement pipeline")
    parser.add_argument("--species", default="all",
                        help="Species slug or 'all'")
    parser.add_argument("--sf2", type=Path, default=DEFAULT_SF2,
                        help="Path to .sf2 soundfont file")
    args = parser.parse_args()

    if not FLUIDSYNTH or not Path(FLUIDSYNTH).exists():
        sys.exit("fluidsynth not found — run: brew install fluidsynth")
    if not args.sf2.exists():
        sys.exit(f"Soundfont not found: {args.sf2}")
    if not LIBRARY.exists():
        sys.exit(f"MIDI library not found: {LIBRARY}")

    # Collect target species dirs
    if args.species == "all":
        dirs = sorted(d for d in LIBRARY.iterdir() if d.is_dir())
    else:
        slug = slugify(args.species)
        d = LIBRARY / slug
        if not d.exists():
            sys.exit(f"Species folder not found: {d}")
        dirs = [d]

    total = len(dirs)
    ok_count = 0

    if ERROR_LOG.exists():
        ERROR_LOG.unlink()

    print(f"\nNatureTunes arrange — {total} species | SF2: {args.sf2.name}\n")

    for i, species_dir in enumerate(dirs, 1):
        print(f"  [{i:02d}/{total}] {species_dir.name}...", end=" ", flush=True)
        success, msg = process_species(species_dir, args.sf2)
        status = msg.split("]")[0].strip("[")   # OK / SKIP / ERR
        rest   = msg.split("→")[-1].strip() if "→" in msg else msg.split("—")[-1].strip()
        if success:
            ok_count += 1
            print(f"✓  → {rest}")
        else:
            print(f"✗  {rest}")

    print(f"\n  Done: {ok_count}/{total} arranged → output/arranged/")
    if ERROR_LOG.exists():
        print(f"  Errors logged to: {ERROR_LOG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
