"""
Generate realistic synthetic CICIDS2017-style data (20 features) and train ensemble model.
Run from project root: python backend/scripts/generate_and_train.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score, confusion_matrix, precision_score, recall_score
import joblib

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EDA_REPORT_PATH = Path("backend/reports/eda_report.json")
MI_THRESHOLD = 0.05  # Ngưỡng Mutual Information Score để giữ lại đặc trưng

FEATURES = [
    "flow_duration", "total_fwd_packets", "total_bwd_packets",
    "total_fwd_bytes", "total_bwd_bytes", "avg_packet_size",
    "packet_rate", "byte_rate", "syn_count", "fin_count",
    "rst_count", "psh_count", "ack_count", "unique_dst_ports",
    "inter_arrival_time_mean", "fwd_packet_rate", "bwd_packet_rate",
    "fwd_byte_rate", "bwd_byte_rate", "packet_length_mean",
]

N = 10_000  # total samples
rng = np.random.default_rng(42)


def _make(n, **kw):
    return {k: v(n) for k, v in kw.items()}


def generate(n=N):
    classes = {
        "Normal": (int(n * 0.50), dict(
            flow_duration   = lambda n: rng.exponential(1.0, n),
            total_fwd_packets = lambda n: rng.integers(5, 80, n).astype(float),
            total_bwd_packets = lambda n: rng.integers(3, 60, n).astype(float),
            total_fwd_bytes = lambda n: rng.uniform(500, 50_000, n),
            total_bwd_bytes = lambda n: rng.uniform(300, 40_000, n),
            avg_packet_size = lambda n: rng.uniform(64, 1400, n),
            packet_rate     = lambda n: rng.uniform(10, 500, n),
            byte_rate       = lambda n: rng.uniform(1_000, 100_000, n),
            syn_count       = lambda n: rng.integers(0, 3, n).astype(float),
            fin_count       = lambda n: rng.integers(0, 3, n).astype(float),
            rst_count       = lambda n: rng.integers(0, 2, n).astype(float),
            psh_count       = lambda n: rng.integers(1, 10, n).astype(float),
            ack_count       = lambda n: rng.integers(3, 30, n).astype(float),
            unique_dst_ports= lambda n: rng.integers(1, 5, n).astype(float),
            inter_arrival_time_mean = lambda n: rng.uniform(0.005, 0.1, n),
            fwd_packet_rate = lambda n: rng.uniform(5, 250, n),
            bwd_packet_rate = lambda n: rng.uniform(3, 200, n),
            fwd_byte_rate   = lambda n: rng.uniform(500, 50_000, n),
            bwd_byte_rate   = lambda n: rng.uniform(300, 40_000, n),
            packet_length_mean = lambda n: rng.uniform(64, 1400, n),
        )),
        "DDoS": (int(n * 0.20), dict(
            flow_duration   = lambda n: rng.exponential(0.2, n),
            total_fwd_packets = lambda n: rng.integers(200, 2000, n).astype(float),
            total_bwd_packets = lambda n: rng.integers(0, 20, n).astype(float),
            total_fwd_bytes = lambda n: rng.uniform(10_000, 500_000, n),
            total_bwd_bytes = lambda n: rng.uniform(0, 5_000, n),
            avg_packet_size = lambda n: rng.uniform(40, 200, n),
            packet_rate     = lambda n: rng.uniform(5_000, 50_000, n),
            byte_rate       = lambda n: rng.uniform(500_000, 5_000_000, n),
            syn_count       = lambda n: rng.integers(100, 1000, n).astype(float),
            fin_count       = lambda n: rng.integers(0, 5, n).astype(float),
            rst_count       = lambda n: rng.integers(0, 10, n).astype(float),
            psh_count       = lambda n: rng.integers(0, 5, n).astype(float),
            ack_count       = lambda n: rng.integers(0, 20, n).astype(float),
            unique_dst_ports= lambda n: rng.integers(1, 3, n).astype(float),
            inter_arrival_time_mean = lambda n: rng.uniform(0.00001, 0.001, n),
            fwd_packet_rate = lambda n: rng.uniform(4_000, 40_000, n),
            bwd_packet_rate = lambda n: rng.uniform(0, 100, n),
            fwd_byte_rate   = lambda n: rng.uniform(400_000, 4_000_000, n),
            bwd_byte_rate   = lambda n: rng.uniform(0, 2_000, n),
            packet_length_mean = lambda n: rng.uniform(40, 200, n),
        )),
        "PortScan": (int(n * 0.15), dict(
            flow_duration   = lambda n: rng.uniform(0.001, 0.5, n),
            total_fwd_packets = lambda n: rng.integers(1, 5, n).astype(float),
            total_bwd_packets = lambda n: rng.integers(0, 2, n).astype(float),
            total_fwd_bytes = lambda n: rng.uniform(40, 500, n),
            total_bwd_bytes = lambda n: rng.uniform(0, 200, n),
            avg_packet_size = lambda n: rng.uniform(40, 80, n),
            packet_rate     = lambda n: rng.uniform(100, 2_000, n),
            byte_rate       = lambda n: rng.uniform(1_000, 20_000, n),
            syn_count       = lambda n: rng.integers(1, 3, n).astype(float),
            fin_count       = lambda n: rng.integers(0, 1, n).astype(float),
            rst_count       = lambda n: rng.integers(0, 3, n).astype(float),
            psh_count       = lambda n: rng.integers(0, 2, n).astype(float),
            ack_count       = lambda n: rng.integers(0, 3, n).astype(float),
            unique_dst_ports= lambda n: rng.integers(50, 1000, n).astype(float),
            inter_arrival_time_mean = lambda n: rng.uniform(0.0001, 0.01, n),
            fwd_packet_rate = lambda n: rng.uniform(100, 2_000, n),
            bwd_packet_rate = lambda n: rng.uniform(0, 500, n),
            fwd_byte_rate   = lambda n: rng.uniform(500, 10_000, n),
            bwd_byte_rate   = lambda n: rng.uniform(0, 2_000, n),
            packet_length_mean = lambda n: rng.uniform(40, 80, n),
        )),
        "BruteForce": (int(n * 0.08), dict(
            flow_duration   = lambda n: rng.uniform(0.5, 10.0, n),
            total_fwd_packets = lambda n: rng.integers(10, 100, n).astype(float),
            total_bwd_packets = lambda n: rng.integers(8, 80, n).astype(float),
            total_fwd_bytes = lambda n: rng.uniform(500, 10_000, n),
            total_bwd_bytes = lambda n: rng.uniform(400, 8_000, n),
            avg_packet_size = lambda n: rng.uniform(100, 600, n),
            packet_rate     = lambda n: rng.uniform(20, 200, n),
            byte_rate       = lambda n: rng.uniform(2_000, 50_000, n),
            syn_count       = lambda n: rng.integers(5, 50, n).astype(float),
            fin_count       = lambda n: rng.integers(1, 10, n).astype(float),
            rst_count       = lambda n: rng.integers(0, 5, n).astype(float),
            psh_count       = lambda n: rng.integers(5, 30, n).astype(float),
            ack_count       = lambda n: rng.integers(10, 80, n).astype(float),
            unique_dst_ports= lambda n: rng.integers(1, 3, n).astype(float),
            inter_arrival_time_mean = lambda n: rng.uniform(0.01, 0.5, n),
            fwd_packet_rate = lambda n: rng.uniform(10, 100, n),
            bwd_packet_rate = lambda n: rng.uniform(8, 80, n),
            fwd_byte_rate   = lambda n: rng.uniform(1_000, 20_000, n),
            bwd_byte_rate   = lambda n: rng.uniform(800, 16_000, n),
            packet_length_mean = lambda n: rng.uniform(100, 600, n),
        )),
        "Botnet": (int(n * 0.07), dict(
            flow_duration   = lambda n: rng.uniform(5.0, 60.0, n),
            total_fwd_packets = lambda n: rng.integers(20, 200, n).astype(float),
            total_bwd_packets = lambda n: rng.integers(15, 150, n).astype(float),
            total_fwd_bytes = lambda n: rng.uniform(1_000, 30_000, n),
            total_bwd_bytes = lambda n: rng.uniform(800, 25_000, n),
            avg_packet_size = lambda n: rng.uniform(80, 400, n),
            packet_rate     = lambda n: rng.uniform(5, 50, n),
            byte_rate       = lambda n: rng.uniform(500, 10_000, n),
            syn_count       = lambda n: rng.integers(0, 5, n).astype(float),
            fin_count       = lambda n: rng.integers(0, 5, n).astype(float),
            rst_count       = lambda n: rng.integers(0, 3, n).astype(float),
            psh_count       = lambda n: rng.integers(3, 20, n).astype(float),
            ack_count       = lambda n: rng.integers(10, 100, n).astype(float),
            unique_dst_ports= lambda n: rng.integers(1, 10, n).astype(float),
            inter_arrival_time_mean = lambda n: rng.uniform(0.1, 2.0, n),
            fwd_packet_rate = lambda n: rng.uniform(3, 30, n),
            bwd_packet_rate = lambda n: rng.uniform(2, 25, n),
            fwd_byte_rate   = lambda n: rng.uniform(300, 8_000, n),
            bwd_byte_rate   = lambda n: rng.uniform(200, 6_000, n),
            packet_length_mean = lambda n: rng.uniform(80, 400, n),
        )),
    }

    frames = []
    for label, (count, generators) in classes.items():
        df = pd.DataFrame({f: gen(count) for f, gen in generators.items()})
        df["Label"] = label
        frames.append(df)

    df = pd.concat(frames, ignore_index=True).sample(frac=1, random_state=42).reset_index(drop=True)

    # Add realistic noise (5% Gaussian noise on all numeric features)
    noise_scale = 0.05
    for col in FEATURES:
        col_std = df[col].std()
        df[col] = df[col] + rng.normal(0, col_std * noise_scale, len(df))
        df[col] = df[col].clip(lower=0)  # no negative values

    logger.info("Generated %d samples | distribution:\n%s", len(df), df["Label"].value_counts().to_string())
    return df


def get_filtered_features(all_features: list[str], mi_threshold: float) -> list[str]:
    """
    Tải báo cáo EDA và lọc các đặc trưng dựa trên Mutual Information Score.
    """
    if not EDA_REPORT_PATH.exists():
        logger.warning(
            f"Báo cáo EDA không tìm thấy tại {EDA_REPORT_PATH}. "
            "Sử dụng TẤT CẢ các đặc trưng mặc định."
        )
        return all_features

    with open(EDA_REPORT_PATH, "r", encoding="utf-8") as f:
        eda_report = json.load(f)

    mi_scores = eda_report.get("mutual_information", {})
    if not mi_scores:
        logger.warning("Không tìm thấy MI scores trong báo cáo EDA. Sử dụng TẤT CẢ các đặc trưng mặc định.")
        return all_features

    filtered = [feat for feat, score in mi_scores.items() if score >= mi_threshold]
    logger.info(f"Đã lọc {len(filtered)} đặc trưng với MI Score >= {mi_threshold} (từ {len(all_features)} đặc trưng gốc).")
    return filtered


def train(df: pd.DataFrame, feature_names: list[str]):
    """Huấn luyện mô hình với tập đặc trưng đã cho."""
    X = df[feature_names]
    y = df["Label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    encoder = LabelEncoder()
    y_train_e = encoder.fit_transform(y_train)

    clf = RandomForestClassifier(
        n_estimators=200, max_depth=15, class_weight="balanced",
        n_jobs=-1, random_state=42
    )
    clf.fit(X_train_s, y_train_e)

    y_pred_e = clf.predict(X_test_s)
    y_pred   = encoder.inverse_transform(y_pred_e)

    acc = accuracy_score(y_test, y_pred)
    f1  = f1_score(y_test, y_pred, average="macro")
    prec = precision_score(y_test, y_pred, average="macro", zero_division=0)
    rec = recall_score(y_test, y_pred, average="macro", zero_division=0)
    report = classification_report(y_test, y_pred, output_dict=True)
    cm = confusion_matrix(y_test, y_pred, labels=encoder.classes_)

    # Calculate False Positive Rate for Normal class
    cm_normal_idx = list(encoder.classes_).index("Normal") if "Normal" in encoder.classes_ else 0
    fp = cm.sum(axis=0)[cm_normal_idx] - cm[cm_normal_idx, cm_normal_idx]
    tn = cm.sum() - (cm.sum(axis=0)[cm_normal_idx] + cm.sum(axis=1)[cm_normal_idx] - cm[cm_normal_idx, cm_normal_idx])
    fpr = float(fp) / (fp + tn) if (fp + tn) > 0 else 0.0

    logger.info("Test accuracy : %.4f", acc)
    logger.info("Test precision: %.4f", prec)
    logger.info("Test recall   : %.4f", rec)
    logger.info("Test F1 macro : %.4f", f1)
    logger.info("Test FPR      : %.4f", fpr)
    logger.info("\n%s", classification_report(y_test, y_pred))

    return clf, scaler, encoder, {
        "accuracy": acc,
        "precision_macro": prec,
        "recall_macro": rec,
        "f1_macro": f1,
        "false_positive_rate": fpr,
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
    }


def plot_feature_importance(clf, feature_names: list[str]):
    """Vẽ biểu đồ độ quan trọng của các đặc trưng."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib không được cài đặt, bỏ qua bước vẽ biểu đồ.")
        return

    importances = clf.feature_importances_
    indices = np.argsort(importances)

    plt.figure(figsize=(10, 8))
    plt.title("Feature Importances (Random Forest)")
    plt.barh(range(len(indices)), importances[indices], color="#3b82f6", align="center")
    plt.yticks(range(len(indices)), [feature_names[i] for i in indices])
    plt.xlabel("Relative Importance")
    plt.tight_layout()

    figures_dir = Path("backend/reports/figures")
    figures_dir.mkdir(parents=True, exist_ok=True)
    out_path = figures_dir / "feature_importance.png"
    plt.savefig(out_path, dpi=120)
    plt.close()
    logger.info(f"Đã lưu biểu đồ Feature Importance → {out_path}")


def save_artifacts(clf, scaler, encoder, metrics):
    models_dir = Path("backend/models")
    models_dir.mkdir(exist_ok=True)

    joblib.dump(clf,     models_dir / "ensemble.pkl")
    joblib.dump(scaler,  models_dir / "ensemble_scaler.pkl")
    joblib.dump(encoder, models_dir / "ensemble_encoder.pkl")

    # Update features.json with training date
    features_path = models_dir / "features.json"
    with open(features_path) as f:
        feat_data = json.load(f)
    feat_data["trained_date"] = pd.Timestamp.now().isoformat() # Sử dụng datetime.now().isoformat() nếu không dùng pandas
    with open(features_path, "w") as f:
        json.dump(feat_data, f, indent=2)

    # Save training report
    report_path = Path("backend/reports") / "cicids2017_training_report.json"
    report_path.parent.mkdir(exist_ok=True)
    report = {
        "training_date": pd.Timestamp.now().isoformat(),
        "dataset_path": "backend/data/cicids2017_processed.csv",
        "dataset_shape": [N, 20],
        "model_type": "ensemble",
        "n_features": len(FEATURES), # Cập nhật số lượng features thực tế
        "feature_names": FEATURES,
        "n_classes": len(clf.classes_),
        "class_names": list(encoder.classes_),
        "train_samples": int(N * 0.8),
        "test_samples":  int(N * 0.2),
        "metrics": {
            "accuracy":            round(metrics["accuracy"], 4),
            "precision_macro":     round(metrics["precision_macro"], 4),
            "recall_macro":        round(metrics["recall_macro"], 4),
            "f1_macro":            round(metrics["f1_macro"], 4),
            "false_positive_rate": round(metrics["false_positive_rate"], 4),
            "confusion_matrix":    metrics["confusion_matrix"],
            "class_names":         list(encoder.classes_),
            "classification_report": metrics["classification_report"],
        },
        "model_params": {
            "algorithm":    "RandomForestClassifier",
            "n_estimators": 200,
            "max_depth":    15,
            "class_weight": "balanced",
            "random_state": 42,
        },
    }
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info("Artifacts saved → models/ensemble*.pkl")
    logger.info("Report saved   → %s", report_path)


if __name__ == "__main__":
    logger.info("=== Step 1: Generate synthetic CICIDS2017-style data ===")
    df = generate(N)

    # Save processed CSV (overwrite dummy)
    out_csv = Path("backend/data/cicids2017_processed.csv")
    df.to_csv(out_csv, index=False)
    logger.info(f"Saved → {out_csv} ({len(df)} rows)")

    # Lọc đặc trưng dựa trên MI Score
    selected_features = get_filtered_features(FEATURES, MI_THRESHOLD)
    # Cập nhật biến FEATURES toàn cục để các hàm khác sử dụng tập đặc trưng đã lọc
    FEATURES = selected_features

    logger.info("=== Step 2: Train ensemble model ===")
    clf, scaler, encoder, metrics = train(df, FEATURES)

    # Thêm bước mô hình hóa feature importance
    plot_feature_importance(clf, FEATURES)

    logger.info("=== Step 3: Save artifacts ===")
    save_artifacts(clf, scaler, encoder, metrics)

    logger.info("=== Done! ===")
    logger.info("Accuracy: %.4f | F1 macro: %.4f", metrics["accuracy"], metrics["f1_macro"])
