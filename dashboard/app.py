"""
dashboard/app.py — NatureTunes local MIDI/MP3 browser.

Usage:
  cd /path/to/BirdMind
  python dashboard/app.py                          # uses data/midi_library/
  python dashboard/app.py --library /custom/path   # custom library folder
  python dashboard/app.py --port 8080              # custom port (default 5050)
"""

import argparse
import mimetypes
import os
from pathlib import Path

from flask import Flask, abort, render_template, send_file

# ── config ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
DEFAULT_LIBRARY = ROOT / "data" / "midi_library"

app = Flask(__name__, template_folder="templates")
LIBRARY_PATH: Path = DEFAULT_LIBRARY  # overridden by --library flag

# ── scanning ──────────────────────────────────────────────────────────────────

def _fmt_size(n_bytes: int) -> str:
    if n_bytes < 1024:
        return f"{n_bytes} B"
    if n_bytes < 1024 ** 2:
        return f"{n_bytes / 1024:.1f} KB"
    return f"{n_bytes / 1024 ** 2:.1f} MB"


def _mp3_duration(path: Path) -> str | None:
    try:
        from mutagen.mp3 import MP3
        audio = MP3(str(path))
        secs = int(audio.info.length)
        return f"{secs // 60}:{secs % 60:02d}"
    except Exception:
        return None


def scan_library(library: Path) -> list[dict]:
    """
    Walk library root. Each immediate subdirectory = one species.
    Accepts any .mid and .mp3 files found inside (picks first of each type).
    """
    entries = []
    if not library.exists():
        return entries

    for species_dir in sorted(library.iterdir()):
        if not species_dir.is_dir():
            continue

        files = list(species_dir.iterdir())
        mid_files = sorted(f for f in files if f.suffix == ".mid")
        mp3_files = sorted(f for f in files if f.suffix == ".mp3")

        if not mid_files and not mp3_files:
            continue

        mid = mid_files[0] if mid_files else None
        mp3 = mp3_files[0] if mp3_files else None

        # Human-readable species name from folder slug
        species_name = species_dir.name.replace("_", " ").title()

        entries.append({
            "species":      species_name,
            "slug":         species_dir.name,
            "mid_name":     mid.name if mid else None,
            "mid_size":     _fmt_size(mid.stat().st_size) if mid else None,
            "mp3_name":     mp3.name if mp3 else None,
            "mp3_size":     _fmt_size(mp3.stat().st_size) if mp3 else None,
            "duration":     _mp3_duration(mp3) if mp3 else None,
            "has_mid":      mid is not None,
            "has_mp3":      mp3 is not None,
        })

    return entries


# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    entries = scan_library(LIBRARY_PATH)
    total   = len(entries)
    n_mid   = sum(1 for e in entries if e["has_mid"])
    n_mp3   = sum(1 for e in entries if e["has_mp3"])
    return render_template(
        "index.html",
        entries=entries,
        total=total,
        n_mid=n_mid,
        n_mp3=n_mp3,
        library_path=str(LIBRARY_PATH),
    )


@app.route("/audio/<slug>/<filename>")
def serve_audio(slug: str, filename: str):
    """Stream the MP3 for inline playback."""
    path = LIBRARY_PATH / slug / filename
    if not path.exists() or path.suffix != ".mp3":
        abort(404)
    return send_file(str(path), mimetype="audio/mpeg")


@app.route("/download/<slug>/<filename>")
def download_midi(slug: str, filename: str):
    """Force-download the MIDI file."""
    path = LIBRARY_PATH / slug / filename
    if not path.exists() or path.suffix != ".mid":
        abort(404)
    return send_file(str(path), mimetype="audio/midi", as_attachment=True,
                     download_name=filename)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NatureTunes MIDI Library Dashboard")
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY,
                        help="Path to the midi_library folder")
    parser.add_argument("--port", type=int, default=5050)
    args = parser.parse_args()

    LIBRARY_PATH = args.library
    port = int(os.environ.get("PORT", args.port))
    print(f"\n  NatureTunes Dashboard — http://localhost:{port}")
    print(f"  Library: {LIBRARY_PATH}\n")
    app.run(debug=False, port=port, host="0.0.0.0")
