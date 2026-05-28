"""
Preprocess CICIDS2017 v2 (bvk/CICIDS-2017 format)
==================================================
Map 89 columns trong CSV của bvk/CICIDS-2017 → 20 features của project.

Usage:
    python backend/scripts/preprocess_cicids2017_v2.py

Output:
    backend/data/cicids2017_processed.csv
    backend/reports/cicids2017_preprocess_report.json
"""

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INPUT_DIR = Path("backend/data/cicids2017")
OUTPUT_CSV = Path("backend/data/cicids2017_processed.csv")
REPORT_PATH = Path("backend/reports/cicids2017_preprocess_report.json")

# Mapping từ CICIDS2017 columns → 20 features của project
FEATURE_MAPPING = {
    "flow_duration":           "Flow Duration",
    "total_fwd_packets":       "Total Fwd Packet",
    "total_bwd_packets":       "Total Bwd packets",
    "total_fwd_bytes":         "Total Length of Fwd Packet",
    "total_bwd_bytes":         "Total Length of Bwd Packet",
    "avg_packet_size":         "Average Packet Size",
    "packet_rate":             "Flow Packets/s",
    "byte_rate":               "Flow Bytes/s",
    "syn_count":               "SYN Flag Count",
    "fin_count":               "FIN Flag Count",
    "rst_count":               "RST Flag Count",
    "psh_count":               "PSH Flag Count",
    "ack_count":               "ACK Flag Count",
    # Các features cần derive
    "unique_dst_ports":        None,  # CICIDS2017 không có, default = 1
    "inter_arrival_time_mean": "Flow IAT Mean",
    "fwd_packet_rate":         "Fwd Packets/s",
    "bwd_packet_rate":         "Bwd Packets/s",
    "fwd_byte_rate":           None,  # = total_fwd_bytes / flow_duration
    "bwd_byte_rate":           None,  # = total_bwd_bytes / flow_duration
    "packet_length_mean":      "Packet Length Mean",
}

# Map labels CICIDS2017 → 6 classes của project
LABEL_MAPPING = {
    "BENIGN":                            "Normal",
    "DDoS":                              "DDoS",
    "DoS Hulk":                          "DDoS",
    "DoS Hulk - Attempted":              "DDoS",
    "DoS GoldenEye":                     "DDoS",
    "DoS GoldenEye - Attempted":         "DDoS",
    "DoS slowloris":                     "DDoS",
    "DoS Slowloris":                     "DDoS",
    "DoS Slowloris - Attempted":         "DDoS",
    "DoS Slowhttptest":                  "DDoS",
    "DoS Slowhttptest - Attempted":      "DDoS",
    "Heartbleed":                        "DDoS",
    "PortScan":                          "PortScan",
    "Portscan":                          "PortScan",
    "Infiltration - Portscan":           "PortScan",
    "FTP-Patator":                       "BruteForce",
    "FTP-Patator - Attempted":           "BruteForce",
    "SSH-Patator":                       "BruteForce",
    "SSH-Patator - Attempted":           "BruteForce",
    "Web Attack \x96 Brute Force":       "BruteForce",
    "Web Attack - Brute Force":          "BruteForce",
    "Web Attack - Brute Force - Attempted": "BruteForce",
    "Web Attack \x96 XSS":               "Abnormal",
    "Web Attack - XSS":                  "Abnormal",
    "Web Attack - XSS - Attempted":      "Abnormal",
    "Web Attack \x96 Sql Injection":     "Abnormal",
    "Web Attack - Sql Injection":        "Abnormal",
    "Web Attack - SQL Injection":        "Abnormal",
    "Web Attack - SQL Injection - Attempted": "Abnormal",
    "Bot":                               "Botnet",
    "Botnet":                            "Botnet",
    "Botnet - Attempted":                "Botnet",
    "Infiltration":                      "Abnormal",
    "Infiltration - Attempted":          "Abnormal",
}


def load_all_csvs(input_dir: Path) -> pd.DataFrame:
    """Load tất cả CSV files (trừ dummy) và merge."""
    csvs = sorted([f for f in input_dir.glob("*.csv") if f.name != "dummy_data.csv"])
    if not csvs:
        raise FileNotFoundError(f"No CSV files found in {input_dir}")

    logger.info(f"Loading {len(csvs)} CSV files:")
    frames = []
    for f in csvs:
        size_mb = f.stat().st_size / 1024 / 1024
        logger.info(f"  Loading {f.name} ({size_mb:.1f} MB)...")
        df = pd.read_csv(f, low_memory=False)
        logger.info(f"    Shape: {df.shape}")
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    logger.info(f"Combined shape: {combined.shape}")
    return combined


def map_features(df: pd.DataFrame) -> pd.DataFrame:
    """Map CICIDS2017 columns → 20 features của project."""
    logger.info("Mapping features...")
    out = pd.DataFrame()

    for target, source in FEATURE_MAPPING.items():
        if source is not None and source in df.columns:
            out[target] = df[source]
        else:
            out[target] = 0.0

    # Derive: unique_dst_ports — chỉ có 1 dst_port per flow trong CICIDS2017
    out["unique_dst_ports"] = 1

    # Derive: fwd_byte_rate = total_fwd_bytes / flow_duration (microseconds)
    flow_dur_sec = df["Flow Duration"].replace(0, 1) / 1_000_000  # μs → s
    out["fwd_byte_rate"] = df["Total Length of Fwd Packet"] / flow_dur_sec
    out["bwd_byte_rate"] = df["Total Length of Bwd Packet"] / flow_dur_sec

    # Convert flow_duration from microseconds to seconds (project format)
    out["flow_duration"] = out["flow_duration"] / 1_000_000

    return out


def map_labels(df: pd.DataFrame) -> pd.Series:
    """Map labels CICIDS2017 → project labels."""
    if "Label" not in df.columns:
        raise ValueError("'Label' column not found")

    labels = df["Label"].astype(str).str.strip()

    # Apply mapping
    mapped = labels.map(LABEL_MAPPING)

    # Log unmapped labels
    unmapped = labels[mapped.isna()].unique()
    if len(unmapped) > 0:
        logger.warning(f"Unmapped labels (sẽ thành 'Abnormal'): {unmapped}")
        mapped = mapped.fillna("Abnormal")

    return mapped


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean NaN, Inf, negative values."""
    logger.info("Cleaning data...")
    n_before = len(df)

    # Replace inf
    df = df.replace([np.inf, -np.inf], np.nan)

    # Drop rows với NaN
    df = df.dropna()

    # Clip negative values to 0
    feature_cols = [c for c in df.columns if c != "Label"]
    df[feature_cols] = df[feature_cols].clip(lower=0)

    n_after = len(df)
    logger.info(f"  Dropped {n_before - n_after} rows ({n_before} → {n_after})")
    return df


def balance_dataset(df: pd.DataFrame, max_samples_per_class: int = 50000) -> pd.DataFrame:
    """Balance dataset: cap mỗi class tối đa N samples (CICIDS2017 rất imbalanced)."""
    logger.info(f"Balancing dataset (max {max_samples_per_class:,} per class)...")
    balanced_frames = []
    for label in df["Label"].unique():
        subset = df[df["Label"] == label]
        if len(subset) > max_samples_per_class:
            subset = subset.sample(n=max_samples_per_class, random_state=42)
        balanced_frames.append(subset)
        logger.info(f"  {label:15s}: {len(subset):,} samples")

    balanced = pd.concat(balanced_frames, ignore_index=True)
    return balanced.sample(frac=1, random_state=42).reset_index(drop=True)


def main():
    if not INPUT_DIR.exists():
        logger.error(f"Input directory not found: {INPUT_DIR}")
        logger.error("Run: python backend/scripts/download_cicids2017.py")
        return 1

    # Load all CSVs
    raw = load_all_csvs(INPUT_DIR)

    # Distribution gốc
    if "Label" in raw.columns:
        logger.info(f"Raw label distribution:\n{raw['Label'].value_counts().to_string()}")

    # Map features
    features = map_features(raw)
    features["Label"] = map_labels(raw)

    # Distribution sau mapping
    logger.info(f"\nMapped label distribution:\n{features['Label'].value_counts().to_string()}")

    # Clean
    features = clean_data(features)

    # Balance
    features = balance_dataset(features)

    # Save processed CSV
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(OUTPUT_CSV, index=False)
    logger.info(f"\n✅ Saved processed CSV → {OUTPUT_CSV}")
    logger.info(f"   Shape: {features.shape}")

    # Save report
    report = {
        "preprocessing_date": pd.Timestamp.now().isoformat(),
        "source_files": [f.name for f in INPUT_DIR.glob("*.csv") if f.name != "dummy_data.csv"],
        "raw_rows": len(raw),
        "processed_rows": len(features),
        "n_features": 20,
        "feature_names": list(FEATURE_MAPPING.keys()),
        "class_distribution": features["Label"].value_counts().to_dict(),
        "label_mapping_applied": {k: v for k, v in LABEL_MAPPING.items() if v},
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"✅ Saved report → {REPORT_PATH}")

    logger.info("\nNext step:")
    logger.info("  python backend/ml/train_flow_model.py \\")
    logger.info("    --data backend/data/cicids2017_processed.csv \\")
    logger.info("    --model ensemble")

    return 0


if __name__ == "__main__":
    sys.exit(main())
