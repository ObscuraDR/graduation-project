"""
Exploratory Data Analysis (EDA) — CICIDS2017 Dataset
=====================================================
Phân tích statistical và visualization cho dataset CICIDS2017.

Output: backend/reports/eda_report.json + matplotlib plots trong backend/reports/figures/

Usage:
    python backend/scripts/eda_cicids2017.py
    python backend/scripts/eda_cicids2017.py --data backend/data/cicids2017_processed.csv
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif
from sklearn.preprocessing import LabelEncoder

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("backend/reports")
FIGURES_DIR = OUTPUT_DIR / "figures"


def basic_stats(df: pd.DataFrame) -> dict:
    """Thống kê cơ bản."""
    logger.info("Computing basic statistics...")
    return {
        "n_rows": len(df),
        "n_columns": len(df.columns),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
        "missing_values": df.isna().sum().to_dict(),
        "duplicate_rows": int(df.duplicated().sum()),
    }


def class_distribution(df: pd.DataFrame, label_col: str = "Label") -> dict:
    """Phân bố các class."""
    if label_col not in df.columns:
        return {"error": f"Column '{label_col}' not found"}
    counts = df[label_col].value_counts()
    total = len(df)
    return {
        "total_samples": total,
        "n_classes": len(counts),
        "class_counts": counts.to_dict(),
        "class_percentages": {k: round(v / total * 100, 2) for k, v in counts.items()},
        "imbalance_ratio": round(counts.max() / counts.min(), 2) if counts.min() > 0 else None,
    }


def feature_statistics(df: pd.DataFrame, label_col: str = "Label") -> dict:
    """Thống kê từng feature: mean, std, min, max, percentiles."""
    feature_cols = [c for c in df.columns if c != label_col]
    stats = {}
    for col in feature_cols:
        if df[col].dtype.kind in "biufc":
            stats[col] = {
                "mean": round(df[col].mean(), 4),
                "std": round(df[col].std(), 4),
                "min": round(df[col].min(), 4),
                "max": round(df[col].max(), 4),
                "median": round(df[col].median(), 4),
                "p25": round(df[col].quantile(0.25), 4),
                "p75": round(df[col].quantile(0.75), 4),
                "skewness": round(df[col].skew(), 4),
                "kurtosis": round(df[col].kurtosis(), 4),
            }
    return stats


def correlation_analysis(df: pd.DataFrame, label_col: str = "Label") -> dict:
    """Tính correlation matrix giữa features."""
    feature_cols = [c for c in df.columns if c != label_col and df[c].dtype.kind in "biufc"]
    corr = df[feature_cols].corr()

    # Tìm cặp features có correlation cao (|r| > 0.8)
    high_corr_pairs = []
    for i in range(len(feature_cols)):
        for j in range(i + 1, len(feature_cols)):
            r = corr.iloc[i, j]
            if abs(r) > 0.8:
                high_corr_pairs.append({
                    "feature_1": feature_cols[i],
                    "feature_2": feature_cols[j],
                    "correlation": round(r, 4),
                })

    return {
        "feature_count": len(feature_cols),
        "high_correlation_pairs": sorted(
            high_corr_pairs, key=lambda x: abs(x["correlation"]), reverse=True
        ),
    }


def calculate_mutual_information(df: pd.DataFrame, label_col: str = "Label") -> dict:
    """Tính toán Mutual Information Score giữa features và label."""
    logger.info("Calculating Mutual Information scores (this may take a minute)...")
    
    feature_cols = [c for c in df.columns if c != label_col and df[c].dtype.kind in "biufc"]
    X = df[feature_cols]
    
    # Encode label thành số để dùng với mutual_info_classif
    le = LabelEncoder()
    y = le.fit_transform(df[label_col])
    
    # Tính toán MI scores
    scores = mutual_info_classif(X, y, random_state=42)
    
    mi_results = {feat: round(score, 4) for feat, score in zip(feature_cols, scores)}
    # Sắp xếp theo thứ tự giảm dần
    return dict(sorted(mi_results.items(), key=lambda item: item[1], reverse=True))


def plot_mutual_information(mi_scores: dict):
    """Vẽ biểu đồ Mutual Information Score."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    
    features = list(mi_scores.keys())
    scores = list(mi_scores.values())

    plt.figure(figsize=(12, 8))
    bars = plt.barh(features[::-1], scores[::-1], color="#10b981")
    plt.xlabel("Mutual Information Score")
    plt.title("Feature Dependency with Label (Mutual Information)")
    
    for bar in bars:
        plt.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height()/2, 
                 f'{bar.get_width():.3f}', va='center', fontsize=9)

    plt.tight_layout()
    out = FIGURES_DIR / "mutual_information.png"
    plt.savefig(out, dpi=120)
    plt.close()
    logger.info(f"Saved → {out}")


def plot_class_distribution(df: pd.DataFrame, label_col: str = "Label"):
    """Vẽ bar chart class distribution."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed, skipping plots")
        return

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    counts = df[label_col].value_counts()

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(counts.index, counts.values, color="#3b82f6")
    ax.set_xlabel("Attack Class")
    ax.set_ylabel("Number of Samples")
    ax.set_title("CICIDS2017 — Class Distribution")
    ax.tick_params(axis="x", rotation=30)

    # Thêm giá trị lên đỉnh mỗi bar
    for bar, val in zip(bars, counts.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2, val,
            f"{val:,}", ha="center", va="bottom", fontsize=9,
        )

    plt.tight_layout()
    out = FIGURES_DIR / "class_distribution.png"
    plt.savefig(out, dpi=120)
    plt.close()
    logger.info(f"Saved → {out}")


def plot_feature_distributions(df: pd.DataFrame, label_col: str = "Label", top_n: int = 6):
    """Vẽ histogram cho top N features có variance cao nhất."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    feature_cols = [c for c in df.columns if c != label_col and df[c].dtype.kind in "biufc"]
    # Lấy top N features có std cao nhất
    top_features = df[feature_cols].std().sort_values(ascending=False).head(top_n).index.tolist()

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for ax, feat in zip(axes.flat, top_features):
        df[feat].plot.hist(ax=ax, bins=50, color="#8b5cf6", alpha=0.7)
        ax.set_title(feat)
        ax.set_yscale("log")  # log scale vì distribution thường skewed

    plt.suptitle("Feature Distributions (top variance)")
    plt.tight_layout()
    out = FIGURES_DIR / "feature_distributions.png"
    plt.savefig(out, dpi=120)
    plt.close()
    logger.info(f"Saved → {out}")


def plot_correlation_heatmap(df: pd.DataFrame, label_col: str = "Label"):
    """Vẽ correlation heatmap."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    feature_cols = [c for c in df.columns if c != label_col and df[c].dtype.kind in "biufc"]
    corr = df[feature_cols].corr()

    fig, ax = plt.subplots(figsize=(14, 12))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(feature_cols)))
    ax.set_yticks(range(len(feature_cols)))
    ax.set_xticklabels(feature_cols, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(feature_cols, fontsize=9)
    plt.colorbar(im, ax=ax)
    ax.set_title("Feature Correlation Heatmap")
    plt.tight_layout()
    out = FIGURES_DIR / "correlation_heatmap.png"
    plt.savefig(out, dpi=120)
    plt.close()
    logger.info(f"Saved → {out}")


def main():
    parser = argparse.ArgumentParser(description="EDA for CICIDS2017 dataset")
    parser.add_argument(
        "--data",
        default="backend/data/cicids2017_processed.csv",
        help="Path to processed CSV file",
    )
    parser.add_argument(
        "--output",
        default="backend/reports/eda_report.json",
        help="Path to output JSON report",
    )
    parser.add_argument("--no-plots", action="store_true", help="Skip plot generation")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        logger.error(f"Dataset not found: {data_path}")
        logger.info("Run: python backend/scripts/generate_and_train.py")
        return

    logger.info(f"Loading dataset: {data_path}")
    df = pd.read_csv(data_path)
    logger.info(f"Loaded shape: {df.shape}")

    logger.info("=== EDA Pipeline ===")
    report = {
        "dataset_path": str(data_path),
        "basic_stats": basic_stats(df),
        "class_distribution": class_distribution(df),
        "feature_statistics": feature_statistics(df),
        "correlation_analysis": correlation_analysis(df),
        "mutual_information": calculate_mutual_information(df),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"Report saved → {args.output}")

    if not args.no_plots:
        logger.info("Generating plots...")
        plot_class_distribution(df)
        plot_feature_distributions(df)
        plot_correlation_heatmap(df)
        plot_mutual_information(report["mutual_information"])

    # Print summary
    cd = report["class_distribution"]
    logger.info("=== Summary ===")
    logger.info(f"Total samples : {cd.get('total_samples')}")
    logger.info(f"Classes       : {cd.get('n_classes')}")
    logger.info(f"Imbalance     : {cd.get('imbalance_ratio')}x")
    logger.info(f"High-corr pairs: {len(report['correlation_analysis']['high_correlation_pairs'])}")
    logger.info("Done!")


if __name__ == "__main__":
    main()
