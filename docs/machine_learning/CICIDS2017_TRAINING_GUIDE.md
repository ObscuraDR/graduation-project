# CICIDS2017 Training Guide

Hướng dẫn train ML models từ dataset CICIDS2017 cho Z-Sentinel IDS.

---

## Yêu cầu

### Dataset

Download CICIDS2017 từ nguồn chính thức:
- **URL:** https://www.unb.ca/cic/datasets/ids-2017.html
- **Format:** CSV files (GeneratedLabelledFlows)
- **Đặt vào:** `data/cicids2017/` (tạo thư mục nếu chưa có)

### Dependencies

```bash
pip install pandas numpy scikit-learn joblib xgboost
# Đã có trong requirements.txt
```

---

## Quick Start (Windows PowerShell)

```powershell
# Chạy toàn bộ pipeline tự động
.\scripts\train_cicids2017.ps1 -InputDir "data\cicids2017" -ModelType "ensemble"
```

**Parameters:**

| Tham số | Bắt buộc | Mặc định | Mô tả |
|---|---|---|---|
| `-InputDir` | ✅ | — | Thư mục chứa CICIDS2017 CSV files |
| `-OutputCsv` | ❌ | `data/cicids2017_processed.csv` | Output processed CSV |
| `-ModelType` | ❌ | `rf` | `rf`, `xgb`, hoặc `ensemble` |
| `-OutputDir` | ❌ | `models` | Thư mục lưu model artifacts |
| `-TestSize` | ❌ | `0.5` | Tỷ lệ test set |

---

## Manual Training Steps

### Bước 1: Preprocess Dataset

```bash
python backend/scripts/preprocess_cicids2017.py \
  --input-dir backend/data/cicids2017 \
  --output backend/data/cicids2017_processed.csv
```

**Output:**
- `data/cicids2017_processed.csv` — 20 feature columns + Label
- `reports/cicids2017_preprocess_report.json` — preprocessing statistics

**Verify:**
```bash
python -c "
import pandas as pd
df = pd.read_csv('data/cicids2017_processed.csv')
print('Shape:', df.shape)
print('Columns:', df.columns.tolist())
print('Label distribution:')
print(df['Label'].value_counts())
"
```

**Expected columns (21 total = 20 features + Label):**
```
flow_duration, total_fwd_packets, total_bwd_packets, total_fwd_bytes,
total_bwd_bytes, avg_packet_size, packet_rate, byte_rate, syn_count,
fin_count, rst_count, psh_count, ack_count, unique_dst_ports,
inter_arrival_time_mean, fwd_packet_rate, bwd_packet_rate, fwd_byte_rate,
bwd_byte_rate, packet_length_mean, Label
```

**Preprocessing report fields:**
```json
{
  "total_rows_loaded": 2830743,
  "total_rows_kept": 2815234,
  "dropped_rows_count": 15509,
  "class_distribution": {
    "Normal": 2273097,
    "DDoS": 128027,
    "PortScan": 158930,
    "BruteForce": 13835,
    "Botnet": 1966,
    "Abnormal": 239379
  },
  "missing_columns_handled": [...]
}
```

### Bước 2: Train Model

```bash
# Train ensemble (RandomForest)
python backend/ml/train_flow_model.py \
  --data data/cicids2017_processed.csv \
  --model ensemble \
  --output-dir models

# Train Random Forest
python backend/ml/train_flow_model.py \
  --data data/cicids2017_processed.csv \
  --model rf

# Train XGBoost
python backend/ml/train_flow_model.py \
  --data data/cicids2017_processed.csv \
  --model xgb
```

**Console output mẫu:**
```
============================================================
STARTING TRAINING PIPELINE
============================================================
Loading dataset from data/cicids2017_processed.csv
Loaded dataset with shape (2815234, 21)
Label distribution:
  Normal: 2273097
  DDoS: 128027
  PortScan: 158930
  ...
Splitting data with test_size=0.5...
  Train set: 1407617 samples
  Test set:  1407617 samples
Scaling features...
Training ensemble model...
Model training complete

============================================================
EVALUATION METRICS
============================================================
Accuracy:          0.9XXX
Precision (macro): 0.9XXX
Recall (macro):    0.9XXX
F1 Score (macro):  0.9XXX
FPR (Normal):      0.0XXX

Saving artifacts to models/...
  Saved: models/ensemble.pkl
  Saved: models/ensemble_scaler.pkl
  Saved: models/ensemble_encoder.pkl
  Updated: models/features.json
  Saved: reports/cicids2017_training_report.json
============================================================
TRAINING PIPELINE COMPLETE
============================================================
```

**Model artifacts sau khi train:**

```
models/
├── ensemble.pkl           # Trained RandomForest classifier
├── ensemble_scaler.pkl    # StandardScaler (fitted on training data)
├── ensemble_encoder.pkl   # LabelEncoder (class names)
└── features.json          # Feature contract (20 features, fixed order)
```

### Bước 3: Verify Model Loading

```bash
python -c "
from backend.detection_engine.model_loader import get_model_loader
import json

loader = get_model_loader('models')
success = loader.load_from_directory('ensemble')

if success:
    info = loader.get_model_info()
    print('✅ Model loaded successfully')
    print(f'   Type: {info[\"model_type\"]}')
    print(f'   Features: {info[\"n_features\"]}')
    print(f'   Classes: {info[\"class_names\"]}')

    with open('reports/cicids2017_training_report.json') as f:
        report = json.load(f)
    print(f'   Accuracy: {report[\"metrics\"][\"accuracy\"]:.4f}')
    print(f'   F1 (macro): {report[\"metrics\"][\"f1_macro\"]:.4f}')
    print(f'   FPR: {report[\"metrics\"][\"false_positive_rate\"]:.4f}')
else:
    print('❌ Failed to load model')
"
```

**Expected output:**
```
✅ Model loaded successfully
   Type: sklearn
   Features: 20
   Classes: ['Botnet', 'BruteForce', 'DDoS', 'Normal', 'PortScan', 'Abnormal']
   Accuracy: 0.9XXX
   F1 (macro): 0.9XXX
   FPR: 0.0XXX
```

### Bước 4: Validate Feature Contract

```bash
python backend/scripts/validate_features.py
# Expected: [PASS] Feature contract valid: 20 features match
```

### Bước 5: Smoke Test Inference

```bash
python backend/scripts/test_predictor.py
# Expected: Prediction successful, attack_type returned
```

---

## Training Report Structure

`reports/cicids2017_training_report.json`:

```json
{
  "training_date": "2026-05-22T10:00:00",
  "dataset_path": "data/cicids2017_processed.csv",
  "dataset_shape": [2815234, 21],
  "model_type": "ensemble",
  "n_features": 20,
  "feature_names": ["flow_duration", "total_fwd_packets", "..."],
  "n_classes": 6,
  "class_names": ["Botnet", "BruteForce", "DDoS", "Normal", "PortScan", "Abnormal"],
  "train_samples": 1407617,
  "test_samples": 1407617,
  "test_size": 0.5,
  "random_state": 42,
  "metrics": {
    "accuracy": 0.9XXX,
    "precision_macro": 0.9XXX,
    "recall_macro": 0.9XXX,
    "f1_macro": 0.9XXX,
    "false_positive_rate": 0.0XXX,
    "confusion_matrix": [[...], [...]],
    "class_names": ["Botnet", "BruteForce", "DDoS", "Normal", "PortScan", "Abnormal"],
    "per_class_metrics": [
      {"class": "Normal", "precision": 0.9XXX, "recall": 0.9XXX, "f1": 0.9XXX, "support": N},
      {"class": "DDoS",   "precision": 0.9XXX, "recall": 0.9XXX, "f1": 0.9XXX, "support": N}
    ]
  },
  "model_params": {
    "n_estimators": 100,
    "max_depth": 10,
    "class_weight": "balanced",
    "max_features": "sqrt",
    "criterion": "gini",
    "random_state": 42
  }
}
```

---

## Model Hyperparameters

| Parameter | Value | Lý do |
|---|---|---|
| `n_estimators` | 100 | Balance giữa accuracy và training time |
| `max_depth` | 10 | Tránh overfitting |
| `class_weight` | `"balanced"` | Xử lý class imbalance (Normal >> Attack) |
| `max_features` | `"sqrt"` | Standard cho RandomForest |
| `criterion` | `"gini"` | Default, hiệu quả |
| `random_state` | 42 | Reproducibility |
| `test_size` | 0.5 | 50/50 split cho evaluation robust |

---

## Feature Contract

File `models/features.json` định nghĩa thứ tự cố định của 20 features:

```json
{
  "n_features": 20,
  "feature_names": [
    "flow_duration",
    "total_fwd_packets",
    "total_bwd_packets",
    "total_fwd_bytes",
    "total_bwd_bytes",
    "avg_packet_size",
    "packet_rate",
    "byte_rate",
    "syn_count",
    "fin_count",
    "rst_count",
    "psh_count",
    "ack_count",
    "unique_dst_ports",
    "inter_arrival_time_mean",
    "fwd_packet_rate",
    "bwd_packet_rate",
    "fwd_byte_rate",
    "bwd_byte_rate",
    "packet_length_mean"
  ]
}
```

**Quan trọng:** Thứ tự này phải khớp chính xác với `FeatureExtractor.feature_names` trong `backend/feature_engine/feature_extractor.py`. `Predictor` validate điều này khi khởi động và raise `FeatureContractError` nếu không khớp.

---

## Dummy Models (Dev/Demo — không cần dataset)

Nếu chưa có CICIDS2017, dùng dummy models để test pipeline:

```bash
python backend/ml/create_dummy_models.py
```

Tạo RandomForest nhỏ (5 estimators) trained trên synthetic data. **Không dùng cho production** — accuracy thấp, chỉ để verify pipeline hoạt động.

---

## Troubleshooting

### "No CSV files found"
```
Kiểm tra đường dẫn --input-dir có chứa file .csv không
ls data/cicids2017/*.csv
```

### "Dataset is missing required features"
```
Preprocessing chưa hoàn thành hoặc CICIDS2017 column names khác
Kiểm tra: python -c "import pandas as pd; print(pd.read_csv('data/cicids2017/Monday-WorkingHours.pcap_ISCX.csv').columns.tolist())"
```

### "FeatureContractError" khi load model
```
features.json không khớp với feature_extractor.py
Chạy: python backend/scripts/validate_features.py
```

### Low accuracy / High FPR
```
- Kiểm tra class distribution trong preprocessing report
- Thử model khác: --model xgb
- Tăng n_estimators trong train_flow_model.py
- Kiểm tra data quality (NaN/Inf rows dropped)
```

### Training quá chậm
```
- Giảm n_estimators xuống 50
- Dùng subset: thêm --sample-size 100000 (nếu script hỗ trợ)
- Dùng XGBoost thay RandomForest (thường nhanh hơn)
```

---

## Integration với Backend

Sau khi train xong, backend tự động dùng models mới:

1. `ModelLoader.load_from_directory("ensemble")` load từ `models/`
2. `Predictor` validate feature contract với `models/features.json`
3. Không cần thay đổi code — chỉ cần restart backend

```bash
# Restart backend để load models mới
docker compose restart ids-backend

# Verify
curl http://localhost:8000/health/detailed
# model_loaded: true
```

---

## Next Steps sau Training

1. Xem training report: `cat backend/reports/cicids2017_training_report.json`
2. Validate feature contract: `python backend/scripts/validate_features.py`
3. Smoke test: `python backend/scripts/test_predictor.py`
4. Restart backend: `docker compose restart ids-backend`
5. Verify health: `curl http://localhost:8000/health/detailed`
6. Start pipeline và test với real traffic
7. Monitor FPR (False Positive Rate) — mục tiêu < 5%
