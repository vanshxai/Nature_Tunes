#!/usr/bin/env python3
"""BirdMind prototype dataset exploration report.

Loads data/prototype/prototype_metadata.csv and prints / saves a full
exploration report. Pure CSV analysis — pandas + numpy only.

Run:
    /opt/miniconda3/envs/birdmind/bin/python explore_dataset.py
"""

import io
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "prototype" / "prototype_metadata.csv"
REPORT_PATH = BASE_DIR / "data" / "prototype" / "exploration_report.txt"

# Tee output to both stdout and the report file.
_buffer = io.StringIO()


def out(*args, **kwargs):
    print(*args, **kwargs)
    print(*args, **kwargs, file=_buffer)


def hr(title=""):
    out("\n" + "=" * 78)
    if title:
        out(title)
        out("=" * 78)


def section(title):
    out("\n" + "-" * 78)
    out(title)
    out("-" * 78)


def main():
    df = pd.read_csv(CSV_PATH)
    n = len(df)

    hr("BirdMind Prototype Dataset — Exploration Report")
    out(f"Source : {CSV_PATH}")
    out(f"Records: {n}")
    out(f"Species: {df.common_name.nunique()}")
    out(f"Total duration: {df.duration.sum()/3600:.1f} hours "
        f"({df.duration.sum():.0f} seconds)")

    # -------------------------------------------------------------------
    # 1. Per-species breakdown
    # -------------------------------------------------------------------
    section("1. PER-SPECIES BREAKDOWN")
    g = df.groupby("common_name")
    per = pd.DataFrame({
        "files": g.size(),
        "avg_dur_s": g.duration.mean(),
        "min_dur": g.duration.min(),
        "max_dur": g.duration.max(),
        "avg_freq_Hz": g.dominant_freq_hz.mean(),
        "avg_tempo_BPM": g.tempo_bpm.mean(),
        "avg_silence": g.silence_ratio.mean(),
    }).round(1)
    per = per.sort_values("files", ascending=False)
    per_disp = per.copy()
    per_disp["avg_dur_s"] = per_disp["avg_dur_s"].map("{:.0f}".format)
    per_disp["avg_freq_Hz"] = per_disp["avg_freq_Hz"].map("{:.0f}".format)
    per_disp["avg_tempo_BPM"] = per_disp["avg_tempo_BPM"].map("{:.0f}".format)
    per_disp["avg_silence"] = per_disp["avg_silence"].map("{:.2f}".format)
    per_disp["min_dur"] = per_disp["min_dur"].map("{:.0f}".format)
    per_disp["max_dur"] = per_disp["max_dur"].map("{:.0f}".format)
    out(per_disp.to_string())

    # -------------------------------------------------------------------
    # 2. Frequency tier distribution
    # -------------------------------------------------------------------
    section("2. FREQUENCY TIER DISTRIBUTION")
    freq_bins = [-np.inf, 2000, 5000, np.inf]
    freq_labels = ["LOW (<2000Hz)", "MID (2000-5000Hz)", "HIGH (>5000Hz)"]
    df["freq_tier"] = pd.cut(df.dominant_freq_hz, bins=freq_bins, labels=freq_labels)

    out("Overall:")
    overall_freq = df.freq_tier.value_counts().reindex(freq_labels).fillna(0).astype(int)
    for lbl in freq_labels:
        c = overall_freq[lbl]
        out(f"  {lbl:<20} {c:>4}  ({c/n*100:5.1f}%)")

    out("\nPer species (file counts):")
    freq_ct = pd.crosstab(df.common_name, df.freq_tier).reindex(columns=freq_labels, fill_value=0)
    out(freq_ct.to_string())

    # -------------------------------------------------------------------
    # 3. Tempo distribution
    # -------------------------------------------------------------------
    section("3. TEMPO DISTRIBUTION")
    tempo_bins = [-np.inf, 60, 80, 100, 120, np.inf]
    tempo_labels = ["Very Slow (<60)", "Slow (60-80)", "Medium (80-100)",
                    "Fast (100-120)", "Very Fast (>120)"]
    df["tempo_band"] = pd.cut(df.tempo_bpm, bins=tempo_bins, labels=tempo_labels)

    out("Overall:")
    overall_tempo = df.tempo_band.value_counts().reindex(tempo_labels).fillna(0).astype(int)
    for lbl in tempo_labels:
        c = overall_tempo[lbl]
        out(f"  {lbl:<20} {c:>4}  ({c/n*100:5.1f}%)")

    out("\nPer species (file counts):")
    tempo_ct = pd.crosstab(df.common_name, df.tempo_band).reindex(columns=tempo_labels, fill_value=0)
    out(tempo_ct.to_string())

    # -------------------------------------------------------------------
    # 4. Silence ratio distribution
    # -------------------------------------------------------------------
    section("4. SILENCE RATIO DISTRIBUTION")
    sil_bins = [-np.inf, 0.2, 0.5, np.inf]
    sil_labels = ["Dense (<0.2)", "Moderate (0.2-0.5)", "Sparse (>0.5)"]
    df["sil_band"] = pd.cut(df.silence_ratio, bins=sil_bins, labels=sil_labels)

    out("Overall:")
    overall_sil = df.sil_band.value_counts().reindex(sil_labels).fillna(0).astype(int)
    for lbl in sil_labels:
        c = overall_sil[lbl]
        out(f"  {lbl:<20} {c:>4}  ({c/n*100:5.1f}%)")

    out("\nPer species (file counts):")
    sil_ct = pd.crosstab(df.common_name, df.sil_band).reindex(columns=sil_labels, fill_value=0)
    out(sil_ct.to_string())

    # -------------------------------------------------------------------
    # 5. Geographic coverage
    # -------------------------------------------------------------------
    section("5. GEOGRAPHIC COVERAGE")
    out(f"Unique countries: {df.country.nunique()}")
    out("\nTop 10 countries by file count:")
    top_countries = df.country.value_counts().head(10)
    for country, c in top_countries.items():
        out(f"  {country:<28} {c:>4}  ({c/n*100:5.1f}%)")

    # -------------------------------------------------------------------
    # 6. Anomalies
    # -------------------------------------------------------------------
    section("6. ANOMALY FLAGS")
    anomalies = {
        "Duration < 10s": df[df.duration < 10],
        "Duration > 180s": df[df.duration > 180],
        "Dominant freq > 10000 Hz": df[df.dominant_freq_hz > 10000],
        "Dominant freq < 200 Hz": df[df.dominant_freq_hz < 200],
        "Silence ratio > 0.9": df[df.silence_ratio > 0.9],
        "Tempo = 0 (beat-track failed)": df[df.tempo_bpm == 0],
    }
    any_flag = False
    for label, sub in anomalies.items():
        out(f"\n  {label}: {len(sub)} file(s)")
        if len(sub):
            any_flag = True
            show = sub[["xc_id", "common_name", "duration",
                        "dominant_freq_hz", "tempo_bpm", "silence_ratio"]].copy()
            show["dominant_freq_hz"] = show.dominant_freq_hz.round(0)
            show["tempo_bpm"] = show.tempo_bpm.round(1)
            show["silence_ratio"] = show.silence_ratio.round(2)
            out(show.head(15).to_string(index=False))
            if len(sub) > 15:
                out(f"    ... and {len(sub)-15} more")
    if not any_flag:
        out("\n  No anomalies detected.")

    # -------------------------------------------------------------------
    # 7. Top 5 cleanest recordings per species
    # -------------------------------------------------------------------
    section("7. TOP 5 CLEANEST RECORDINGS PER SPECIES (lowest silence ratio)")
    for species in sorted(df.common_name.unique()):
        sub = df[df.common_name == species].nsmallest(5, "silence_ratio")
        out(f"\n  {species}:")
        t = sub[["xc_id", "duration", "dominant_freq_hz", "tempo_bpm", "silence_ratio"]].copy()
        t["dominant_freq_hz"] = t.dominant_freq_hz.round(0)
        t["tempo_bpm"] = t.tempo_bpm.round(1)
        t["silence_ratio"] = t.silence_ratio.round(3)
        out(t.to_string(index=False))

    hr("END OF REPORT")

    REPORT_PATH.write_text(_buffer.getvalue())
    out(f"\n[Saved full report to {REPORT_PATH}]")


if __name__ == "__main__":
    main()
