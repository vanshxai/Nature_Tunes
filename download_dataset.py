#!/usr/bin/env python3
"""BirdMind prototype dataset downloader.

Downloads high-quality song recordings of 15 target bird species from the
Xeno-Canto API v2, then extracts acoustic features with librosa and writes a
consolidated metadata CSV.

Run with the dedicated env:
    /opt/miniconda3/envs/birdmind/bin/python download_dataset.py
"""

import csv
import logging
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

API_BASE = "https://xeno-canto.org/api/3/recordings"
# v3 requires a personal API key. Set it via the XENO_CANTO_API_KEY env var.
# Get one at https://xeno-canto.org/account
API_KEY = os.environ.get("XENO_CANTO_API_KEY", "")

# scientific_name -> common_name (used for the on-disk folder)
SPECIES = {
    "Luscinia megarhynchos": "Common Nightingale",
    "Hylocichla mustelina": "Wood Thrush",
    "Catharus guttatus": "Hermit Thrush",
    "Erithacus rubecula": "European Robin",
    "Turdus merula": "Eurasian Blackbird",
    "Serinus canaria": "Canary",
    "Turdus philomelos": "Song Thrush",
    "Catharus fuscescens": "Veery",
    "Catherpes mexicanus": "Canyon Wren",
    "Toxostoma rufum": "Brown Thrasher",
    "Menura novaehollandiae": "Superb Lyrebird",
    "Zonotrichia albicollis": "White-throated Sparrow",
    "Cuculus micropterus": "Indian Cuckoo",
    "Copsychus saularis": "Oriental Magpie-Robin",
    "Copsychus malabaricus": "White-rumped Shama",
    "Piranga olivacea": "Scarlet Tanager",
    "Piranga ludoviciana": "Western Tanager",
    "Piranga rubra": "Summer Tanager",
    "Thraupis episcopus": "Blue-gray Tanager",
}

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "prototype"
RAW_DIR = DATA_DIR / "raw"
METADATA_CSV = DATA_DIR / "prototype_metadata.csv"
ERROR_LOG = DATA_DIR / "errors.log"

PER_SPECIES_LIMIT = 50
MIN_DURATION = 10      # seconds
MAX_DURATION = 180     # seconds
API_RATE_LIMIT = 1.5   # seconds between API calls
DOWNLOAD_TIMEOUT = 30  # seconds per file
MAX_RETRIES = 3
USER_AGENT = "BirdMind-prototype/1.0 (research dataset downloader)"

# Quality grade ordering (A best). Anything else sorts last.
QUALITY_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}

# ----------------------------------------------------------------------------
# Logging / setup
# ----------------------------------------------------------------------------

logger = logging.getLogger("birdmind")


def setup():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(ERROR_LOG, mode="a")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)


# ----------------------------------------------------------------------------
# Duration parsing
# ----------------------------------------------------------------------------

def parse_length_seconds(length: str):
    """Xeno-Canto 'length' is 'M:SS' or 'H:MM:SS'. Return seconds or None."""
    if not length:
        return None
    parts = length.split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return None
    seconds = 0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


# ----------------------------------------------------------------------------
# API querying
# ----------------------------------------------------------------------------

def fetch_recordings(scientific_name: str, session: requests.Session):
    """Fetch all pages of A-quality recordings for a species."""
    # v3 query syntax: sp:"Genus species" for the scientific name, q:A grade.
    query = f'sp:"{scientific_name}" q:A'
    recordings = []
    page = 1
    num_pages = 1
    while page <= num_pages:
        params = {"query": query, "page": page, "key": API_KEY}
        data = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = session.get(API_BASE, params=params, timeout=DOWNLOAD_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
                break
            except (requests.RequestException, ValueError) as exc:
                logger.error("API query attempt %d/%d failed for %s page %d: %s",
                             attempt, MAX_RETRIES, scientific_name, page, exc)
                time.sleep(API_RATE_LIMIT * attempt)
        if data is None:
            # All retries exhausted (e.g. sustained network outage). Bail on
            # this species rather than silently treating it as zero results.
            logger.error("Giving up on %s after %d API attempts", scientific_name, MAX_RETRIES)
            break
        num_pages = int(data.get("numPages", 1))
        recordings.extend(data.get("recordings", []))
        page += 1
        time.sleep(API_RATE_LIMIT)
    return recordings


def filter_and_rank(recordings):
    """Keep song recordings within duration bounds; rank by quality then id."""
    kept = []
    for rec in recordings:
        rec_type = (rec.get("type") or "").lower()
        if "song" not in rec_type:
            continue
        dur = parse_length_seconds(rec.get("length", ""))
        if dur is None or not (MIN_DURATION <= dur <= MAX_DURATION):
            continue
        rec["_duration"] = dur
        kept.append(rec)

    kept.sort(key=lambda r: (
        QUALITY_ORDER.get((r.get("q") or "").upper(), 99),
        int(r.get("id", 0)) if str(r.get("id", "")).isdigit() else 0,
    ))
    return kept[:PER_SPECIES_LIMIT]


# ----------------------------------------------------------------------------
# Downloading
# ----------------------------------------------------------------------------

def build_download_url(rec):
    """Return an absolute, https download URL for a recording."""
    url = rec.get("file") or ""
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    return url


def download_file(url, dest: Path, session: requests.Session):
    """Download with retries. Returns True on success."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with session.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True) as resp:
                resp.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            fh.write(chunk)
                tmp.replace(dest)
            return True
        except (requests.RequestException, OSError) as exc:
            logger.error("Download attempt %d/%d failed for %s: %s",
                         attempt, MAX_RETRIES, url, exc)
            time.sleep(1.0 * attempt)
    return False


# ----------------------------------------------------------------------------
# Acoustic features
# ----------------------------------------------------------------------------

def extract_features(file_path: Path):
    """Return (dominant_freq_hz, tempo_bpm, silence_ratio) or Nones on failure."""
    import librosa  # imported lazily so the download phase has no hard dep
    try:
        y, sr = librosa.load(str(file_path), sr=None, mono=True)
        if y.size == 0:
            raise ValueError("empty audio")

        # Dominant frequency ~ mean spectral centroid
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        dominant_freq = float(np.mean(centroid))

        # Tempo estimate
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo_bpm = float(np.atleast_1d(tempo)[0])

        # Silence ratio: % of frames with RMS below -40 dBFS
        rms = librosa.feature.rms(y=y)[0]
        db = librosa.amplitude_to_db(rms, ref=np.max(np.abs(y)) or 1.0)
        silence_ratio = float(np.mean(db < -40.0))

        return dominant_freq, tempo_bpm, silence_ratio
    except Exception as exc:  # librosa/audioread raise a variety of errors
        logger.error("Feature extraction failed for %s: %s", file_path, exc)
        return None, None, None


# ----------------------------------------------------------------------------
# Main pipeline
# ----------------------------------------------------------------------------

def main():
    if not API_KEY:
        raise SystemExit(
            "No Xeno-Canto API key. Set XENO_CANTO_API_KEY env var or the "
            "API_KEY constant. Get one at https://xeno-canto.org/account"
        )
    setup()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    metadata_rows = []
    failures = []
    per_species_counts = {}

    for scientific_name, common_name in SPECIES.items():
        print(f"\n=== {common_name} ({scientific_name}) ===")
        species_dir = RAW_DIR / common_name
        species_dir.mkdir(parents=True, exist_ok=True)

        recordings = fetch_recordings(scientific_name, session)
        selected = filter_and_rank(recordings)
        print(f"  {len(recordings)} A-grade results -> {len(selected)} song "
              f"recordings in {MIN_DURATION}-{MAX_DURATION}s")

        downloaded = 0
        for rec in tqdm(selected, desc=f"  {common_name}", unit="file"):
            xc_id = rec.get("id")
            dest = species_dir / f"XC{xc_id}.mp3"

            if not dest.exists():
                url = build_download_url(rec)
                if not url:
                    logger.error("No file URL for XC%s (%s)", xc_id, common_name)
                    failures.append((common_name, xc_id, "no file url"))
                    continue
                ok = download_file(url, dest, session)
                time.sleep(API_RATE_LIMIT)
                if not ok:
                    failures.append((common_name, xc_id, "download failed"))
                    continue

            downloaded += 1
            metadata_rows.append({
                "xc_id": xc_id,
                "common_name": common_name,
                "scientific_name": scientific_name,
                "country": rec.get("cnt", ""),
                "lat": rec.get("lat", ""),
                "lng": rec.get("lon", ""),  # v3 field is 'lon'
                "duration": rec.get("_duration"),
                "recordist": rec.get("rec", ""),
                "license": rec.get("lic", ""),
                "file_path": str(dest.relative_to(BASE_DIR)),
            })

        per_species_counts[common_name] = downloaded

    # ----- Acoustic feature extraction -----
    print("\n=== Extracting acoustic features ===")
    for row in tqdm(metadata_rows, desc="  features", unit="file"):
        fpath = BASE_DIR / row["file_path"]
        freq, tempo, silence = extract_features(fpath)
        row["dominant_freq_hz"] = freq
        row["tempo_bpm"] = tempo
        row["silence_ratio"] = silence

    # ----- Write CSV -----
    fieldnames = [
        "xc_id", "common_name", "scientific_name", "country", "lat", "lng",
        "duration", "recordist", "license", "file_path",
        "dominant_freq_hz", "tempo_bpm", "silence_ratio",
    ]
    df = pd.DataFrame(metadata_rows, columns=fieldnames)
    df.to_csv(METADATA_CSV, index=False, quoting=csv.QUOTE_MINIMAL)

    # ----- Summary -----
    print_summary(per_species_counts, metadata_rows, failures)


def dir_size_bytes(path: Path):
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total


def human_size(num_bytes):
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def print_summary(per_species_counts, metadata_rows, failures):
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print("Files per species:")
    for name, count in per_species_counts.items():
        print(f"  {name:<28} {count}")
    print(f"\nTotal files: {len(metadata_rows)}")
    print(f"Total size on disk: {human_size(dir_size_bytes(RAW_DIR))}")
    print(f"Metadata CSV: {METADATA_CSV}")

    if failures:
        print(f"\nFailed downloads: {len(failures)}")
        for common_name, xc_id, reason in failures:
            print(f"  {common_name} XC{xc_id}: {reason}")
        print(f"See {ERROR_LOG} for details.")
    else:
        print("\nNo failed downloads.")


if __name__ == "__main__":
    main()
