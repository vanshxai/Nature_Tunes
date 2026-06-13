#!/usr/bin/env python3
"""BirdMind prototype composition engine.

Maps a mood to a 3-layer (texture / melody / anchor) birdsong mix and renders
an MP3. Selects source recordings from the prototype dataset by onset and
frequency characteristics, mixes them, and exports the result.

Conda env: `birdmind`. Activate it first:
    conda activate birdmind

Usage:
    python src/compose.py --mood anxiety      # one mood
    python src/compose.py --all               # all five moods in sequence

Programmatic:
    from compose import compose
    path = compose("focus")                   # returns output file path (str)
"""

import argparse
import os
import random
import sys
from datetime import datetime
from pathlib import Path

import librosa
import numpy as np
import pandas as pd
import soundfile as sf
from pydub import AudioSegment

# Point pydub at the conda env's ffmpeg (it isn't always on PATH when the
# interpreter is invoked by absolute path).
_ffmpeg = Path(sys.executable).parent / "ffmpeg"
if _ffmpeg.exists():
    AudioSegment.converter = str(_ffmpeg)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "prototype" / "prototype_metadata.csv"
OUTPUT_DIR = BASE_DIR / "data" / "output"

SR = 22050
FADE_IN_S = 3.0
FADE_OUT_S = 5.0
LAYER_VOLUMES = {"texture": 0.35, "melody": 0.55, "anchor": 0.25}

MOOD_RULES = {
    'anxiety': {
        'texture':  {'onset_density': (2.0, 5.0), 'dominant_freq_hz': (3000, 5500)},
        'melody':   {'onset_density': (1.0, 2.5), 'dominant_freq_hz': (3500, 5000)},
        'anchor':   {'onset_interval_ms': (600, 1000), 'dominant_freq_hz': (3000, 4500)},
        'duration': 60, 'master_volume': 0.7
    },
    'sleep': {
        'texture':  {'onset_density': (1.5, 3.5), 'dominant_freq_hz': (2500, 4500)},
        'melody':   {'onset_density': (0.5, 2.0), 'dominant_freq_hz': (3000, 4500)},
        'anchor':   {'onset_interval_ms': (700, 1200), 'dominant_freq_hz': (3000, 4200)},
        'duration': 90, 'master_volume': 0.5
    },
    'focus': {
        'texture':  {'onset_density': (2.5, 5.0), 'dominant_freq_hz': (4000, 6000)},
        'melody':   {'onset_density': (1.5, 3.0), 'dominant_freq_hz': (4000, 5500)},
        'anchor':   {'onset_interval_ms': (400, 700), 'dominant_freq_hz': (3500, 5000)},
        'duration': 60, 'master_volume': 0.8
    },
    'sadness': {
        'texture':  {'onset_density': (1.0, 3.0), 'dominant_freq_hz': (3000, 4500)},
        'melody':   {'onset_density': (0.5, 1.5), 'dominant_freq_hz': (3000, 4200)},
        'anchor':   {'onset_interval_ms': (700, 1000), 'dominant_freq_hz': (3000, 4000)},
        'duration': 75, 'master_volume': 0.6
    },
    'energy': {
        'texture':  {'onset_density': (3.0, 5.0), 'dominant_freq_hz': (4500, 6500)},
        'melody':   {'onset_density': (2.0, 4.0), 'dominant_freq_hz': (4000, 6000)},
        'anchor':   {'onset_interval_ms': (300, 600), 'dominant_freq_hz': (4000, 5500)},
        'duration': 60, 'master_volume': 0.9
    }
}

LAYER_ORDER = ["texture", "melody", "anchor"]


# ---------------------------------------------------------------------------
# Step 1 — data loading
# ---------------------------------------------------------------------------

def load_usable_metadata():
    df = pd.read_csv(CSV_PATH)
    df = df[df["usable"] == True].copy()  # noqa: E712
    return df


# ---------------------------------------------------------------------------
# Step 3 — bird selection
# ---------------------------------------------------------------------------

def _filter_candidates(df, constraints):
    """Return rows matching all numeric (min, max) constraints."""
    mask = pd.Series(True, index=df.index)
    for col, (lo, hi) in constraints.items():
        mask &= df[col].between(lo, hi)
    return df[mask]


def _relax(constraints, factor=0.20):
    """Widen each (min, max) range by `factor` of its span on both ends."""
    relaxed = {}
    for col, (lo, hi) in constraints.items():
        span = hi - lo
        pad = span * factor
        relaxed[col] = (lo - pad, hi + pad)
    return relaxed


def _pick_existing(candidates):
    """Shuffle candidates and return the first whose audio file exists on disk.

    Returns the row (Series) or None if none of the candidates resolve.
    """
    order = list(candidates.index)
    random.shuffle(order)
    for idx in order:
        row = candidates.loc[idx]
        fpath = BASE_DIR / row["file_path"]
        if fpath.exists():
            return row
        print(f"  [skip] missing file on disk: {row['file_path']}")
    return None


def select_for_layer(df, layer_name, constraints):
    """Select one bird recording for a layer, relaxing constraints once."""
    candidates = _filter_candidates(df, constraints)
    row = _pick_existing(candidates) if len(candidates) else None
    if row is None:
        relaxed = _relax(constraints)
        print(f"  [relax] no usable candidate for '{layer_name}' — "
              f"widening constraints by 20% and retrying")
        candidates = _filter_candidates(df, relaxed)
        row = _pick_existing(candidates) if len(candidates) else None
    if row is None:
        raise RuntimeError(
            f"No usable candidate found for layer '{layer_name}' even after relaxing.")
    print(f"  [{layer_name:7s}] {row['common_name']} (XC#{row['xc_id']}) -> "
          f"{row['file_path']}")
    return row


# ---------------------------------------------------------------------------
# Step 4 — audio mixing
# ---------------------------------------------------------------------------

def _load_fit(file_path, target_len):
    """Load audio at SR mono, loop/trim to exactly target_len samples."""
    y, _ = librosa.load(str(file_path), sr=SR, mono=True)
    if y.size == 0:
        y = np.zeros(target_len, dtype=np.float32)
    if len(y) < target_len:
        reps = int(np.ceil(target_len / len(y)))
        y = np.tile(y, reps)
    return y[:target_len].astype(np.float32)


def _apply_fades(y):
    """Apply independent fade-in and fade-out (linear) in place; return y."""
    n_in = min(int(FADE_IN_S * SR), len(y))
    n_out = min(int(FADE_OUT_S * SR), len(y))
    if n_in > 0:
        y[:n_in] *= np.linspace(0.0, 1.0, n_in, dtype=np.float32)
    if n_out > 0:
        y[-n_out:] *= np.linspace(1.0, 0.0, n_out, dtype=np.float32)
    return y


def mix_layers(selected, duration_s, master_volume):
    """Load, fit, fade, volume-scale and sum the three layers. Returns mix."""
    target_len = int(duration_s * SR)
    mix = np.zeros(target_len, dtype=np.float32)
    for layer_name in LAYER_ORDER:
        row = selected[layer_name]
        y = _load_fit(BASE_DIR / row["file_path"], target_len)
        y = _apply_fades(y)
        gain = LAYER_VOLUMES[layer_name] * master_volume
        mix += y * gain
    # Normalize to prevent clipping.
    peak = np.max(np.abs(mix))
    if peak > 0:
        mix = mix / peak * 0.9
    return mix


def export_mp3(mix, out_path):
    """Write WAV via soundfile, convert to MP3 via pydub."""
    wav_tmp = out_path.with_suffix(".wav")
    sf.write(str(wav_tmp), mix, SR)
    AudioSegment.from_wav(str(wav_tmp)).export(str(out_path), format="mp3")
    wav_tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Step 5 — report
# ---------------------------------------------------------------------------

def _print_report(mood, selected, duration_s, out_path):
    tex, mel, anc = selected["texture"], selected["melody"], selected["anchor"]
    rel = out_path.relative_to(BASE_DIR)
    print("\n============================")
    print("BirdMind Composition Report")
    print("============================")
    print(f"Mood        : {mood}")
    print(f"Texture     : {tex['common_name']} (XC#{tex['xc_id']}) — "
          f"{tex['onset_density']:.1f} onsets/s, {tex['dominant_freq_hz']:.0f}Hz")
    print(f"Melody      : {mel['common_name']} (XC#{mel['xc_id']}) — "
          f"{mel['onset_density']:.1f} onsets/s, {mel['dominant_freq_hz']:.0f}Hz")
    print(f"Anchor      : {anc['common_name']} (XC#{anc['xc_id']}) — "
          f"{anc['onset_density']:.1f} onsets/s, {anc['onset_interval_ms']:.0f}ms intervals")
    print(f"Duration    : {duration_s}s")
    print(f"Output file : {rel}")
    print("============================")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compose(mood: str) -> str:
    """Compose one mood mix and return the output file path as a string."""
    if mood not in MOOD_RULES:
        raise ValueError(f"Unknown mood '{mood}'. Choose from {list(MOOD_RULES)}.")

    rules = MOOD_RULES[mood]
    duration_s = rules["duration"]
    master_volume = rules["master_volume"]

    df = load_usable_metadata()
    print(f"\n>>> Composing '{mood}' (duration {duration_s}s, "
          f"master_volume {master_volume}) from {len(df)} usable recordings")

    selected = {}
    for layer_name in LAYER_ORDER:
        selected[layer_name] = select_for_layer(df, layer_name, rules[layer_name])

    mix = mix_layers(selected, duration_s, master_volume)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"{mood}_{timestamp}.mp3"
    export_mp3(mix, out_path)

    _print_report(mood, selected, duration_s, out_path)
    return str(out_path)


def compose_all():
    """Generate all five moods in sequence; return {mood: path}."""
    results = {}
    for mood in MOOD_RULES:
        results[mood] = compose(mood)
    print("\n=== All moods generated ===")
    for mood, path in results.items():
        print(f"  {mood:8s} -> {Path(path).relative_to(BASE_DIR)}")
    return results


def main():
    parser = argparse.ArgumentParser(description="BirdMind composition engine")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--mood", choices=list(MOOD_RULES), help="compose a single mood")
    group.add_argument("--all", action="store_true", help="compose all five moods")
    args = parser.parse_args()

    if args.all:
        compose_all()
    else:
        compose(args.mood)


if __name__ == "__main__":
    main()
