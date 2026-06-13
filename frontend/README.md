# 🌿 NatureTunes

**Music from nature.** A browser-based ambient composer that lets you arrange
real birdsong clips on a timeline, layer a synthesized beat, and share your
composition via a URL.

Built with React 18 + Vite, [Tone.js](https://tonejs.github.io/) for audio
scheduling, and [react-dnd](https://react-dnd.github.io/react-dnd/) for
drag-and-drop. Plain CSS, no UI frameworks, no external CDNs — fully offline
after the initial load (except generating a share link, which uses the page URL).

## Prerequisites

- Node.js 18+ and npm
- Audio assets in `public/audio/` (bird clips, beat loops, and `manifest.json`).
  These are produced by the Python pipeline (`src/prepare_assets.py`) in the
  repository root.

## Develop

```bash
npm install      # install dependencies
npm run dev      # start the Vite dev server (http://localhost:5173)
```

## Build

```bash
npm run build    # production build into dist/
npm run preview  # serve the production build locally to verify
```

The build must complete with zero errors.

## Deploy (Vercel)

`vercel.json` is included with a SPA rewrite so deep links / share URLs resolve
to `index.html`.

```bash
npm install -g vercel   # once
vercel                  # deploy a preview
vercel --prod           # deploy to production
```

Vercel auto-detects Vite. If configuring manually:
- **Build command:** `npm run build`
- **Output directory:** `dist`

## Environment

Copy `.env.example` to `.env` if you want to customise:

```
VITE_APP_NAME=NatureTunes
```

## How it works

- **Bird Library** — drag a bird card onto any timeline slot. Each card shows a
  suggested role (Melody / Texture / Anchor) derived from onset metrics.
- **Timeline** — 4–8 tracks × six 20-second slots (120s total). Drop a bird to
  create a *brick*; click a brick twice to remove it. Each track has a volume
  knob and mute.
- **Beat Pattern** — choose None / Soft / Tribal / Electronic; the BPM slider
  (40–140) drives `Tone.Transport.bpm` live.
- **Play** — schedules every brick at `slotIndex × 20s` on the Tone.js
  Transport; the beat loops from time 0.
- **Share** — encodes the timeline (base64), beat, and BPM into the URL and
  copies it to the clipboard. Opening that URL restores the composition.
- **Admin** — password-gated panel (password: `admin`) showing manifest stats;
  the session persists via `sessionStorage`.
