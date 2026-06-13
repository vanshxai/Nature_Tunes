# 🌿 NatureTunes

Music from nature — birdsong turned into MIDI, composed, and arranged.

This repo contains both the **Python pipeline** (dataset → MIDI → arrangements)
and a single **web app** with two pages:

| Page | Route | What it does |
|------|-------|--------------|
| **Composer** | `/` | Drag-and-drop timeline composer (Tone.js) — layer birdsong clips + beats, share via URL |
| **Library**  | `/library` | Browse all 17 species — play the original recording, play the MIDI as piano, download `.mid`, hear the arranged mix |

The web app is a static Vite + React build — no server needed in production.

## Deploy to Vercel

1. Push this repo to GitHub.
2. In Vercel: **New Project → import the repo**.
3. Set **Root Directory** to `frontend`.
4. Framework preset auto-detects as **Vite** (build `npm run build`, output `dist`).
5. Deploy. The included `frontend/vercel.json` handles SPA deep links (`/library`).

The Library page serves audio/MIDI from `frontend/public/library/`, which is
committed to the repo (~129 MB across 17 species). Raw recordings (1.8 GB) and
soundfonts are gitignored — they aren't needed for the deployed site.

## Local development (web app)

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

## Regenerating the library assets

If you re-run the Python pipeline and want the new MIDI/MP3 to appear in the
web app, regenerate the committed assets + manifest:

```bash
conda activate birdmind
python dashboard/build_static_library.py   # copies into frontend/public/library/
```

## Python pipeline (reference)

Run inside the `birdmind` conda env (Python 3.11):

| Script | Purpose |
|--------|---------|
| `download_dataset.py` | Download recordings from Xeno-Canto |
| `src/bird_to_midi.py` | Convert recordings to MIDI (pyin / basic_pitch) |
| `src/midi_library.py` | Build the best-per-species MIDI library |
| `src/arrange.py` | Layer flute/strings over MIDI, render to MP3 |
| `dashboard/build_static_library.py` | Stage assets for the web app |
| `dashboard/app.py` | Local-only Flask dashboard (superseded by the `/library` page) |
