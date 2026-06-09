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
from datetime import datetime
import logging
import sys
from pathlib import Path
import polars as pl

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


def load_all_csvs(input_dir: Path) -> pl.DataFrame:
    """Load tất cả CSV files (trừ dummy) và merge."""
    csvs = sorted([f for f in input_dir.glob("*.csv") if f.name != "dummy_data.csv"])
    if not csvs:
        raise FileNotFoundError(f"No CSV files found in {input_dir}")

    logger.info(f"Loading {len(csvs)} CSV files:")
    frames = []
    for f in csvs:
        size_mb = f.stat().st_size / 1024 / 1024
        logger.info(f"  Loading {f.name} ({size_mb:.1f} MB)...")
        # Polars đọc CSV rất hiệu quả về bộ nhớ và tốc độ
        df = pl.read_csv(f)
        logger.info(f"    Shape: {df.shape}")
        frames.append(df)

    combined = pl.concat(frames, how="vertical")
    logger.info(f"Combined shape: {combined.shape}")
    return combined


def map_features(df: pl.DataFrame) -> pl.DataFrame:
    """Map CICIDS2017 columns → 20 features của project."""
    logger.info("Mapping features...")
    expressions = []

    for target, source in FEATURE_MAPPING.items():
        if source is not None and source in df.columns:
            expressions.append(pl.col(source).alias(target))
        else:
            expressions.append(pl.lit(0.0).alias(target))

    # Derive: unique_dst_ports — chỉ có 1 dst_port per flow trong CICIDS2017
    expressions.append(pl.lit(1).alias("unique_dst_ports"))

    # Derive: fwd_byte_rate = total_fwd_bytes / flow_duration (microseconds)
    # Xử lý chia cho 0: nếu Flow Duration = 0, dùng 1 để tránh lỗi, sau đó chia cho 1_000_000 để chuyển sang giây
    flow_dur_sec = (
        pl.when(pl.col("Flow Duration") == 0)
        .then(pl.lit(1))
        .otherwise(pl.col("Flow Duration"))
        / 1_000_000
    )
    expressions.append((pl.col("Total Length of Fwd Packet") / flow_dur_sec).alias("fwd_byte_rate"))
    expressions.append((pl.col("Total Length of Bwd Packet") / flow_dur_sec).alias("bwd_byte_rate"))

    out = df.select(expressions)

    # Convert flow_duration from microseconds to seconds (project format)
    out = out.with_columns((pl.col("flow_duration") / 1_000_000).alias("flow_duration"))

    return out


def map_labels(df: pl.DataFrame) -> pl.Series:
    """Map labels CICIDS2017 → project labels."""
    if "Label" not in df.columns:
        raise ValueError("'Label' column not found")

    labels = df["Label"].astype(str).str.strip()

    # Apply mapping
    mapped = labels.map_dict(LABEL_MAPPING)

    # Log unmapped labels
    unmapped = labels.filter(mapped.is_null()).unique().to_list()
    if len(unmapped) > 0:
        logger.warning(f"Unmapped labels (sẽ thành 'Abnormal'): {unmapped}")
        mapped = mapped.fill_null("Abnormal")

    return mapped


def clean_data(df: pl.DataFrame) -> pl.DataFrame:
    """Clean NaN, Inf, negative values."""
    logger.info("Cleaning data...")
    n_before = len(df)

    # Replace inf
    df = df.with_columns(pl.all().replace_inf_with_nan())

    # Drop rows với NaN
    df = df.drop_nulls()

    # Clip negative values to 0
    df = df.with_columns([pl.col(c).clip_min(0) for c in df.columns if c != "Label"])

    n_after = len(df)
    logger.info(f"  Dropped {n_before - n_after} rows ({n_before} → {n_after})")
    return df


def balance_dataset(df: pl.DataFrame, max_samples_per_class: int = 50000) -> pl.DataFrame:
    """Balance dataset: giới hạn mỗi class tối đa N samples (CICIDS2017 rất imbalanced)."""
    logger.info(f"Balancing dataset (max {max_samples_per_class:,} per class)...")
    balanced_frames = []
    for label in df.get_column("Label").unique().to_list():
        subset = df.filter(pl.col("Label") == label)
        if len(subset) > max_samples_per_class:
            subset = subset.sample(n=max_samples_per_class, seed=42, shuffle=True)
        balanced_frames.append(subset)
        logger.info(f"  {label:15s}: {len(subset):,} samples")

    balanced = pl.concat(balanced_frames, how="vertical")
    return balanced.sample(fraction=1.0, seed=42, shuffle=True)


def main():
    if not INPUT_DIR.exists():
        logger.error(f"Input directory not found: {INPUT_DIR}")
        logger.error("Run: python backend/scripts/download_cicids2017.py")
        return 1

    # Load all CSVs
    raw = load_all_csvs(INPUT_DIR)

    # Phân bố nhãn gốc
    if "Label" in raw.columns:
        logger.info(f"Raw label distribution:\n{raw.group_by('Label').len().sort('len', descending=True).to_string()}")

    # Map features
    features = map_features(raw)
    features = features.with_columns(map_labels(raw).alias("Label"))

    # Phân bố nhãn sau mapping
    logger.info(f"\nMapped label distribution:\n{features.group_by('Label').len().sort('len', descending=True).to_string()}")

    # Clean
    features = clean_data(features)

    # Balance
    # Chỉ cân bằng nếu có cột 'Label'
    if "Label" in features.columns:
        features = balance_dataset(features)
    else:
        logger.warning("No 'Label' column found after cleaning, skipping dataset balancing.")

    # Save processed CSV
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    features.write_csv(OUTPUT_CSV)
    logger.info(f"\n✅ Saved processed CSV → {OUTPUT_CSV}")
    logger.info(f"   Shape: {features.shape}")

    # Save report
    class_distribution_df = features.group_by("Label").len().rename({"len": "count"})
    class_distribution_dict = {row["Label"]: row["count"] for row in class_distribution_df.iter_rows(named=True)}

    report = {
        "preprocessing_date": datetime.now().isoformat(),
        "source_files": [f.name for f in INPUT_DIR.glob("*.csv") if f.name != "dummy_data.csv"],
        "raw_rows": len(raw),
        "processed_rows": len(features),
        "n_features": 20,
        "feature_names": list(FEATURE_MAPPING.keys()),
        "class_distribution": class_distribution_dict,
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
