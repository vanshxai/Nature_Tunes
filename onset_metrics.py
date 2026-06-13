#!/usr/bin/env python3
"""Replace tempo detection with bird-appropriate onset metrics.

- Renames tempo_bpm -> librosa_tempo_raw
- Computes onset_interval_ms (median gap between onsets) and onset_density
  (onsets/sec) for usable=True rows.
- Flagged rows (usable=False) and any unreadable files get null metrics.

Run:
    /opt/miniconda3/envs/birdmind/bin/python onset_metrics.py
"""

import logging
from pathlib import Path

import librosa
import numpy as np
import pandas as pd
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "prototype" / "prototype_metadata.csv"
ERROR_LOG = BASE_DIR / "data" / "prototype" / "errors.log"
SR = 22050

logger = logging.getLogger("birdmind.onset")
logger.setLevel(logging.INFO)
_fh = logging.FileHandler(ERROR_LOG, mode="a")
_fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(_fh)


def compute_onset_metrics(file_path: Path):
    """Return (onset_interval_ms, onset_density) or (nan, nan) on failure."""
    y, sr = librosa.load(str(file_path), sr=SR, mono=True)
    if y.size == 0:
        raise ValueError("empty audio")
    duration = librosa.get_duration(y=y, sr=sr)
    onsets = librosa.onset.onset_detect(y=y, sr=sr, backtrack=True, units="time")

    n = len(onsets)
    onset_density = (n / duration) if duration > 0 else np.nan
    if n >= 2:
        interval_ms = float(np.median(np.diff(onsets)) * 1000.0)
    else:
        interval_ms = np.nan
    return interval_ms, onset_density


def main():
    df = pd.read_csv(CSV_PATH)

    # Rename existing tempo column.
    if "tempo_bpm" in df.columns:
        df = df.rename(columns={"tempo_bpm": "librosa_tempo_raw"})

    # Initialise new columns as null for all rows.
    df["onset_interval_ms"] = np.nan
    df["onset_density"] = np.nan

    usable = df[df["usable"] == True]  # noqa: E712  (explicit per spec)
    total = len(usable)
    print(f"Processing {total} usable files (of {len(df)} total)...")

    processed = 0
    missing = 0
    failed = 0
    for count, (idx, row) in enumerate(tqdm(usable.iterrows(), total=total,
                                            desc="onsets", unit="file"), start=1):
        fpath = BASE_DIR / row["file_path"]
        if not fpath.exists():
            missing += 1
            logger.error("Missing file (skipped): %s", fpath)
        else:
            try:
                interval_ms, density = compute_onset_metrics(fpath)
                df.at[idx, "onset_interval_ms"] = interval_ms
                df.at[idx, "onset_density"] = density
                processed += 1
            except Exception as exc:
                failed += 1
                logger.error("Onset extraction failed for %s: %s", fpath, exc)

        if count % 50 == 0:
            print(f"  ...{count}/{total} processed "
                  f"(ok={processed}, missing={missing}, failed={failed})")

    df.to_csv(CSV_PATH, index=False)
    print(f"\nDone. ok={processed}, missing={missing}, failed={failed}")
    print(f"Saved -> {CSV_PATH}")

    # Summary table over usable rows.
    print("\n" + "=" * 78)
    print("PER-SPECIES ONSET SUMMARY (usable files only)")
    print("=" * 78)
    u = df[df["usable"] == True]  # noqa: E712
    g = u.groupby("common_name")
    summary = pd.DataFrame({
        "files": g.size(),
        "avg_onset_interval_ms": g["onset_interval_ms"].mean(),
        "avg_onset_density": g["onset_density"].mean(),
        "interval_null_count": g["onset_interval_ms"].apply(lambda s: int(s.isna().sum())),
    })
    summary["avg_onset_interval_ms"] = summary["avg_onset_interval_ms"].round(1)
    summary["avg_onset_density"] = summary["avg_onset_density"].round(2)
    summary = summary.sort_values("avg_onset_density", ascending=False)
    print(summary.to_string())


if __name__ == "__main__":
    main()
