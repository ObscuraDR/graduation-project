"""
CICIDS2017 Preprocessing Script
===============================
Reads raw CICIDS2017 CSV files, normalizes columns, maps labels,
computes/defaults required features to match the 20-feature IDS contract,
and outputs a single clean processed CSV suitable for training.

Memory is conserved via chunked reading.
"""

import argparse
import glob
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---

FEATURE_CONTRACT_PATH = Path("backend/models/features.json")
REPORT_PATH = Path("backend/reports/cicids2017_preprocess_report.json")

# Label mapping dictionary
LABEL_MAPPING = {
    'BENIGN': 'Normal',
    'DDoS': 'DDoS',
    'PortScan': 'PortScan',
    'FTP-Patator': 'BruteForce',
    'SSH-Patator': 'BruteForce',
    'Web Attack  Brute Force': 'BruteForce',
    'Bot': 'Botnet',
    # Group the rest as Abnormal
    'DoS Hulk': 'Abnormal',
    'DoS GoldenEye': 'Abnormal',
    'DoS slowloris': 'Abnormal',
    'DoS Slowhttptest': 'Abnormal',
    'Web Attack  XSS': 'Abnormal',
    'Web Attack  Sql Injection': 'Abnormal',
    'Infiltration': 'Abnormal',
    'Heartbleed': 'Abnormal'
}

# Try to map normalized CICIDS2017 columns to our target 20 features
# Some we will compute if they don't exist directly.
COLUMN_MAPPING = {
    'flow_duration': 'flow_duration',
    'total_fwd_packets': 'total_fwd_packets',
    'total_backward_packets': 'total_bwd_packets',
    'total_length_of_fwd_packets': 'total_fwd_bytes',
    'total_length_of_bwd_packets': 'total_bwd_bytes',
    'flow_packets_s': 'packet_rate',
    'flow_bytes_s': 'byte_rate',
    'flow_iat_mean': 'inter_arrival_time_mean',
    'fwd_packet_length_mean': 'packet_length_mean',
    # Flags (sometimes named exactly this in CICIDS)
    'syn_flag_count': 'syn_count',
    'fin_flag_count': 'fin_count',
    'rst_flag_count': 'rst_count',
    'psh_flag_count': 'psh_count',
    'ack_flag_count': 'ack_count',
}


def normalize_columns(columns: list) -> list:
    """Strip spaces, lowercase, replace spaces with underscores, remove special chars."""
    norm = []
    for c in columns:
        c = str(c).strip().lower()
        c = c.replace(' ', '_').replace('/', '_').replace('.', '_').replace('-', '_')
        c = ''.join(e for e in c if e.isalnum() or e == '_')
        # Remove consecutive underscores
        while '__' in c:
            c = c.replace('__', '_')
        norm.append(c)
    return norm


def extract_features(df: pd.DataFrame, target_features: list) -> pd.DataFrame:
    """
    Extract exact features. If missing, compute or set default.
    """
    out_df = pd.DataFrame()
    
    for tf in target_features:
        # Check direct mapping
        source_cols = [k for k, v in COLUMN_MAPPING.items() if v == tf]
        found = False
        for sc in source_cols:
            if sc in df.columns:
                out_df[tf] = df[sc]
                found = True
                break
                
        if found:
            continue
            
        # Computations / Defaults if not found directly
        if tf == 'avg_packet_size':
            tot_bytes = df.get('total_length_of_fwd_packets', 0) + df.get('total_length_of_bwd_packets', 0)
            tot_pkts = df.get('total_fwd_packets', 0) + df.get('total_backward_packets', 0)
            out_df[tf] = np.where(tot_pkts > 0, tot_bytes / tot_pkts, 0)
        elif tf == 'unique_dst_ports':
            out_df[tf] = 1  # Not in CICIDS aggregated flow data
        elif tf == 'fwd_packet_rate':
            dur = df.get('flow_duration', 0)
            # Duration in CICIDS is usually microseconds, but let's assume it's just a value
            # If we need it in seconds for rate, usually flow_packets_s is already there.
            # Assuming duration is microseconds as typical in CICIDS:
            out_df[tf] = np.where(dur > 0, df.get('total_fwd_packets', 0) / (dur / 1e6), 0)
        elif tf == 'bwd_packet_rate':
            dur = df.get('flow_duration', 0)
            out_df[tf] = np.where(dur > 0, df.get('total_backward_packets', 0) / (dur / 1e6), 0)
        elif tf == 'fwd_byte_rate':
            dur = df.get('flow_duration', 0)
            out_df[tf] = np.where(dur > 0, df.get('total_length_of_fwd_packets', 0) / (dur / 1e6), 0)
        elif tf == 'bwd_byte_rate':
            dur = df.get('flow_duration', 0)
            out_df[tf] = np.where(dur > 0, df.get('total_length_of_bwd_packets', 0) / (dur / 1e6), 0)
        elif tf in ['syn_count', 'fin_count', 'rst_count', 'psh_count', 'ack_count']:
            out_df[tf] = 0 # Default if flags don't exist
        else:
            out_df[tf] = 0 # Fallback default
            
    return out_df


def map_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Map labels to the 6 target classes. Drops unknown labels."""
    # Find label column
    label_col = None
    for col in df.columns:
        if col.lower() == 'label':
            label_col = col
            break
            
    if not label_col:
        logger.warning("No 'label' column found in chunk!")
        return pd.DataFrame()
        
    df = df.copy()
    
    # First, trim any whitespace or strange chars if needed
    # (Some CICIDS labels have weird encoding issues, e.g. "Web Attack  Brute Force")
    # We will do exact matching against our dict, or partial matching.
    
    def match_label(l):
        l_str = str(l).strip()
        if l_str in LABEL_MAPPING:
            return LABEL_MAPPING[l_str]
        # Partial match fallback for weird encoding
        for k, v in LABEL_MAPPING.items():
            if k.lower() in l_str.lower() or l_str.lower() in k.lower():
                return v
        return 'UNKNOWN'

    df['Label'] = df[label_col].apply(match_label)
    
    # Drop unknowns
    df = df[df['Label'] != 'UNKNOWN']
    
    return df


EXPECTED_FEATURES = [
    "flow_duration", "total_fwd_packets", "total_bwd_packets", "total_fwd_bytes",
    "total_bwd_bytes", "avg_packet_size", "packet_rate", "byte_rate",
    "syn_count", "fin_count", "rst_count", "psh_count", "ack_count",
    "unique_dst_ports", "inter_arrival_time_mean", "fwd_packet_rate",
    "bwd_packet_rate", "fwd_byte_rate", "bwd_byte_rate", "packet_length_mean",
]
MIN_ROWS = 100


def validate_output(output_path: Path) -> None:
    """Strict contract check on the written CSV. Raises ValueError on any violation."""
    df_head = pd.read_csv(output_path, nrows=5)
    actual_cols = list(df_head.columns)

    missing = [f for f in EXPECTED_FEATURES if f not in actual_cols]
    extra = [c for c in actual_cols if c not in EXPECTED_FEATURES and c != "Label"]
    if missing:
        raise ValueError(f"Output CSV missing required feature columns: {missing}")
    if extra:
        raise ValueError(f"Output CSV has unexpected columns: {extra}")
    if "Label" not in actual_cols:
        raise ValueError("Output CSV missing 'Label' column")

    feature_cols = [c for c in actual_cols if c != "Label"]
    if feature_cols != EXPECTED_FEATURES:
        raise ValueError(
            f"Column order mismatch.\n  Expected: {EXPECTED_FEATURES}\n  Got:      {feature_cols}"
        )

    total = sum(1 for _ in open(output_path)) - 1
    if total < MIN_ROWS:
        raise ValueError(
            f"Output CSV has only {total} rows (minimum {MIN_ROWS}). "
            "Check input data or label mapping."
        )
    logger.info(f"Output validation passed: {len(feature_cols)} features, {total} rows, Label present.")


def main():
    parser = argparse.ArgumentParser(description="Preprocess CICIDS2017 dataset")
    parser.add_argument('--input-dir', type=str, required=True, help="Directory containing CICIDS2017 CSV files")
    parser.add_argument('--output', type=str, required=True, help="Output CSV file path")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_path = Path(args.output)
    
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error(f"Input directory does not exist: {input_dir}")
        return

    # Create output dir if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Read feature contract
    if not FEATURE_CONTRACT_PATH.exists():
        logger.error(f"Feature contract not found: {FEATURE_CONTRACT_PATH}")
        return
        
    with open(FEATURE_CONTRACT_PATH, 'r') as f:
        contract = json.load(f)
    target_features = contract['feature_names']
    logger.info(f"Targeting {len(target_features)} features from contract.")

    csv_files = glob.glob(str(input_dir / "*.csv"))
    if not csv_files:
        logger.error(f"No CSV files found in {input_dir}")
        return

    logger.info(f"Found {len(csv_files)} CSV files. Starting processing...")

    total_rows_loaded = 0
    total_rows_kept = 0
    dropped_rows = 0
    class_dist = {}
    
    first_chunk = True

    for file in csv_files:
        logger.info(f"Processing {os.path.basename(file)}...")
        
        try:
            chunk_iterator = pd.read_csv(file, chunksize=100000, low_memory=False)
            
            for chunk in chunk_iterator:
                total_rows_loaded += len(chunk)
                
                # Normalize columns
                chunk.columns = normalize_columns(chunk.columns)
                
                # Map labels and drop unknowns
                chunk = map_labels(chunk)
                if chunk.empty:
                    continue
                    
                # Clean NaNs and Infs in potential feature columns before extraction
                # Replace inf with nan, then drop nans
                chunk = chunk.replace([np.inf, -np.inf], np.nan)
                
                # Drop rows where Label is missing
                chunk = chunk.dropna(subset=['Label'])
                
                # Extract features
                features_df = extract_features(chunk, target_features)
                features_df['Label'] = chunk['Label'].values
                
                # Drop rows where any of the 20 features resulted in NaN during computation
                features_df = features_df.dropna()
                
                kept = len(features_df)
                total_rows_kept += kept
                
                # Update class distribution
                counts = features_df['Label'].value_counts().to_dict()
                for k, v in counts.items():
                    class_dist[k] = class_dist.get(k, 0) + v
                    
                # Append to output
                mode = 'w' if first_chunk else 'a'
                header = first_chunk
                features_df.to_csv(output_path, mode=mode, header=header, index=False)
                first_chunk = False
                
        except Exception as e:
            logger.error(f"Failed to process {file}: {e}")

    dropped_rows = total_rows_loaded - total_rows_kept

    # Generate Report
    report = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "number_of_files": len(csv_files),
        "total_rows_loaded": total_rows_loaded,
        "total_rows_kept": total_rows_kept,
        "dropped_rows_count": dropped_rows,
        "class_distribution": class_dist,
        "missing_columns_handled": [
            "Assumed unique_dst_ports=1",
            "Computed avg_packet_size, and fwd/bwd rates from duration/bytes/packets",
            "Defaulted TCP flags to 0 if not present in chunk"
        ]
    }
    
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, 'w') as f:
        json.dump(report, f, indent=4)
        
    logger.info(f"Processing complete! Kept {total_rows_kept}/{total_rows_loaded} rows.")
    logger.info(f"Output saved to {output_path}")

    # Strict contract validation — raises ValueError and aborts if violated
    validate_output(output_path)

    logger.info(f"Report saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
