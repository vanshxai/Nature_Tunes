"""
build_static_library.py — prepare the MIDI library as static assets for the
combined NatureTunes web app (Vercel-ready).

Copies each species' source MP3 + sample MIDI (and the arranged final MP3, if
present) into frontend/public/library/<slug>/, and writes a manifest JSON the
React Library page reads at runtime.

Usage:
  python dashboard/build_static_library.py
"""

import json
import re
import shutil
from pathlib import Path

ROOT          = Path(__file__).parent.parent
LIBRARY_SRC   = ROOT / "data" / "midi_library"
ARRANGED_SRC  = ROOT / "output" / "arranged"
SEEDS_SRC     = ROOT / "output" / "seeds"
PUBLIC_DIR    = ROOT / "frontend" / "public" / "library"
MANIFEST_PATH = ROOT / "frontend" / "public" / "library_manifest.json"


def human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1024 ** 2:.1f} MB"


def mp3_duration(path: Path) -> str | None:
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(str(path))
        if audio and audio.info and getattr(audio.info, "length", 0):
            secs = int(audio.info.length)
            return f"{secs // 60}:{secs % 60:02d}"
    except Exception:
        pass
    return None


def count_midi_notes(path: Path) -> int:
    try:
        import mido
        mid = mido.MidiFile(str(path))
        return sum(
            1 for trk in mid.tracks for msg in trk
            if msg.type == "note_on" and msg.velocity > 0
        )
    except Exception:
        return 0


def find_one(folder: Path, suffixes: list[str]) -> Path | None:
    for suf in suffixes:
        hits = sorted(folder.glob(f"*{suf}"))
        if hits:
            return hits[0]
    return None


def main() -> None:
    if not LIBRARY_SRC.exists():
        raise SystemExit(f"MIDI library not found: {LIBRARY_SRC}")

    # Fresh public/library dir
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    entries = []
    for species_dir in sorted(d for d in LIBRARY_SRC.iterdir() if d.is_dir()):
        slug = species_dir.name
        mid = find_one(species_dir, ["_sample.mid", "_best.mid", ".mid"])
        mp3 = find_one(species_dir, ["_source.mp3", "_best.mp3", ".mp3"])
        if not mid and not mp3:
            continue

        dest = PUBLIC_DIR / slug
        dest.mkdir(parents=True, exist_ok=True)

        entry = {
            "species": slug.replace("_", " ").title(),
            "slug": slug,
            "mp3": None, "mp3_size": None, "duration": None,
            "mid": None, "mid_size": None, "notes": 0,
            "arranged": None, "arranged_size": None,
            "seed": None, "seed_size": None,
        }

        if mp3:
            out = dest / f"{slug}_source.mp3"
            shutil.copy2(mp3, out)
            entry["mp3"] = f"library/{slug}/{out.name}"
            entry["mp3_size"] = human_size(out.stat().st_size)
            entry["duration"] = mp3_duration(out)

        if mid:
            out = dest / f"{slug}_sample.mid"
            shutil.copy2(mid, out)
            entry["mid"] = f"library/{slug}/{out.name}"
            entry["mid_size"] = human_size(out.stat().st_size)
            entry["notes"] = count_midi_notes(out)

        # Optional arranged final track
        arranged = ARRANGED_SRC / f"{slug}_final.mp3"
        if arranged.exists():
            out = dest / f"{slug}_arranged.mp3"
            shutil.copy2(arranged, out)
            entry["arranged"] = f"library/{slug}/{out.name}"
            entry["arranged_size"] = human_size(out.stat().st_size)

        # Optional seed clip
        seed = SEEDS_SRC / f"{slug}_seed.mp3"
        if seed.exists():
            out = dest / f"{slug}_seed.mp3"
            shutil.copy2(seed, out)
            entry["seed"] = f"library/{slug}/{out.name}"
            entry["seed_size"] = human_size(out.stat().st_size)

        entries.append(entry)
        print(f"  ✓ {slug:<26} mp3={bool(mp3)} mid={bool(mid)} "
              f"arranged={arranged.exists()} seed={seed.exists()} notes={entry['notes']}")

    manifest = {
        "generated": True,
        "count": len(entries),
        "midi_count": sum(1 for e in entries if e["mid"]),
        "mp3_count": sum(1 for e in entries if e["mp3"]),
        "arranged_count": sum(1 for e in entries if e["arranged"]),
        "seed_count": sum(1 for e in entries if e["seed"]),
        "species": entries,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    total_mb = sum(
        f.stat().st_size for f in PUBLIC_DIR.rglob("*") if f.is_file()
    ) / 1024 ** 2
    print(f"\n  {len(entries)} species → {PUBLIC_DIR.relative_to(ROOT)} "
          f"({total_mb:.1f} MB)")
    print(f"  Manifest → {MANIFEST_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
