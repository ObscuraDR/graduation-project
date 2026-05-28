# ML Pipeline Documentation

Machine learning in this project spans **offline training**, **runtime inference** (live pipeline), **legacy REST prediction**, and **SHAP explanations**. All paths and artifacts below exist in the repository or are explicitly expected at runtime.

---

## 1. Feature contract

**Canonical file:** `models/features.json`

```json
{
  "feature_names": [
    "flow_duration",
    "total_fwd_packets",
    "total_bwd_packets",
    ...
    "packet_length_mean"
  ],
  "n_features": 20,
  "version": "1.0"
}
```

**Extractor:** `backend/feature_engine/feature_extractor.py` — `FeatureExtractor.feature_names` must match **name and order**.

**Validation:** `backend/detection_engine/predictor.py`

- `FeatureContractError` on count/order mismatch
- Loads order from `features.json` at `Predictor` init (default path `./backend/models/features.json`)

---

## 2. Runtime inference architecture

```
Flow (flow_builder.py)
    → FeatureExtractor.extract_features()
    → Predictor._validate_features()  # fixed 20-dim vector
    → ModelLoader.predict() / predict_proba()
    → severity + attack_type dict
```

### 2.1 ModelLoader

**File:** `backend/detection_engine/model_loader.py`

| Method | Purpose |
|--------|---------|
| `load_from_directory(model_name)` | Loads `{model_dir}/{name}.pkl`, `{name}_scaler.pkl`, `{name}_encoder.pkl` |
| `load_model(path, scaler_path, encoder_path)` | Explicit paths |
| `predict(features ndarray)` | Applies scaler; sklearn or TensorFlow `.h5` |
| `predict_proba(features)` | Class probabilities |
| `get_class_names()` | From label encoder or `['Normal','Attack']` |

**Singleton:** `get_model_loader(model_dir="./backend/models")`

**Supported artifacts:**

| Extension | Backend |
|-----------|---------|
| `.pkl`, `.joblib` | joblib / sklearn |
| `.h5` | TensorFlow Keras (`backend/ml/lstm_model.py`) |

### 2.2 Predictor

**File:** `backend/detection_engine/predictor.py`

| Method | Purpose |
|--------|---------|
| `predict_flow(flow)` | End-to-end flow prediction |
| `predict_batch(flows)` | Batch inference |
| `is_attack(prediction)` | `attack_type != Normal` and `confidence >= threshold` |
| `_determine_severity()` | Maps confidence to critical/high/medium/low |

Default `confidence_threshold`: **0.75**

**Singleton:** `get_predictor(model_loader=..., confidence_threshold=0.75)`

### 2.3 Pipeline integration

**File:** `backend/pipeline/coordinator.py`

On `initialize()`:

```python
model_loader.load_from_directory(self.model_name)  # default "ensemble"
self.predictor = get_predictor(model_loader=model_loader)
```

On each gated packet:

```python
prediction = self.predictor.predict_flow(flow)
if self.predictor.is_attack(prediction):
    # persist + alert
```

---

## 3. Expected runtime artifacts

**Directory:** `models/` (config: `MODEL_DIR`, default `./backend/models`)

| File pattern | Required for |
|--------------|--------------|
| `ensemble.pkl` | Default pipeline model |
| `ensemble_scaler.pkl` | Feature scaling |
| `ensemble_encoder.pkl` | Label decoding |
| `features.json` | Feature order (in repo) |
| `rf.pkl`, `xgb.pkl`, `lstm.h5` | Optional alternate models per `.env.example` |

**Repository state:** Only `models/features.json` and `models/.gitkeep` are versioned. **Trained weights are not committed.**

Generate artifacts:

```bash
python backend/ml/create_dummy_models.py
# or
python backend/ml/train_flow_model.py --data-path data/cicids2017/processed.csv
# or
python backend/ml/training.py --data-path <csv>
```

Verify:

```bash
python backend/scripts/verify_real_model.py
python backend/scripts/validate_features.py
```

---

## 4. Offline training pipelines

### 4.1 CICIDS2017 preprocessing

**Script:** `scripts/preprocess_cicids2017.py`

- Reads raw CICIDS2017 CSVs (chunked)
- Maps labels via `LABEL_MAPPING` (e.g. `BENIGN` → `Normal`, `PortScan` → `PortScan`)
- Aligns columns to 20-feature contract using `models/features.json`
- Output: processed CSV + `reports/cicids2017_preprocess_report.json`

```bash
python backend/scripts/preprocess_cicids2017.py --input-dir backend/data/cicids2017/raw --output backend/data/cicids2017/processed.csv
```

PowerShell wrapper: `scripts/train_cicids2017.ps1`

### 4.2 Flow model trainer (primary)

**Script:** `backend/ml/train_flow_model.py`  
**Class:** `FlowModelTrainer`

- Expects CSV columns matching `features.json` + label column (default `Label`)
- Trains `RandomForestClassifier` (and can emit ensemble artifacts per script logic)
- Writes `models/{model_type}.pkl`, scaler, encoder, updates `features.json` metadata
- Report: `reports/cicids2017_training_report.json` (when using CICIDS flow)

```bash
python backend/ml/train_flow_model.py --data-path data/cicids2017/processed.csv --model-type ensemble
```

### 4.3 Legacy training CLI

**Script:** `backend/ml/training.py`

- Uses `RandomForestIDS`, `XGBoostIDS`, `EnsembleIDS` from `backend/ml/models.py`
- CLI: `--data-path`, `--model-type` (`rf`, `xgb`, `ensemble`, optional `lstm`)
- Saves to paths from `settings` (`RF_MODEL_PATH`, etc.)

### 4.4 Model class library

**File:** `backend/ml/models.py`

| Class | Algorithm |
|-------|-----------|
| `RandomForestIDS` | sklearn RandomForest |
| `XGBoostIDS` | XGBoost |
| `EnsembleIDS` | VotingClassifier |
| `IDSModel` | Base interface for legacy routes |

Used by:

- `POST /api/models/load/{model_id}` (legacy global `ml_model`)
- `backend/ml/training.py`
- **Not** used by live `ModelLoader` in pipeline (joblib files directly)

### 4.5 LSTM (optional)

**File:** `backend/ml/lstm_model.py`  
TensorFlow Keras sequential model; saves `.h5` + joblib scaler/encoder.

Config path: `LSTM_MODEL_PATH=./backend/models/lstm.h5` in `.env.example`

### 4.6 Dummy models (development)

**File:** `backend/ml/create_dummy_models.py`

Creates minimal sklearn artifacts for local testing without full dataset.

---

## 5. SHAP / XAI flow

**Decoupled from sniffer** — only invoked via HTTP.

| Layer | File |
|-------|------|
| API | `backend/api/routes/xai.py` — `POST /api/xai/explain` |
| Core | `backend/ml/xai.py` — `explain()`, `UnsupportedModelError` |

**Mechanism:**

1. Load feature order from `models/features.json` (cached)
2. `ModelLoader.load_from_directory(model_name)`
3. Extract tree estimator from ensemble (`VotingClassifier` → underlying RF)
4. `shap.TreeExplainer` — cached per `model_name` in `_EXPLAINER_CACHE`
5. Return top-N SHAP features + probabilities

**Limitation:** Tree models only. Non-tree / TensorFlow models raise `UnsupportedModelError`.

---

## 6. Legacy inference module (broken import)

**File:** `backend/ml/inference.py`

```python
from backend.alerts.engine import AlertEngine  # Module does not exist
```

This file is **not** used by `main.py` or the live pipeline. `legacy_routes.py` notes AlertEngine was replaced by `alert_engine/alert_manager.py`.

**Do not run** `python -m backend.ml.inference` without fixing imports.

---

## 7. Inference lifecycle (timeline)

```
Application start
  └─ ModelLoader may NOT be loaded yet

POST /api/sniffer/start
  └─ PipelineCoordinator.initialize()
       └─ load_from_directory("ensemble")
       └─ Predictor validates features.json contract

Per packet (sniffer thread)
  └─ FlowBuilder.add_packet
  └─ [gating] once/window + min_packets
  └─ predict_flow
  └─ if is_attack → DB + Mongo + alert + WS queue

Application stop / POST /api/sniffer/stop
  └─ sniffer thread stopped
  └─ ModelLoader remains loaded in singleton
```

`/health/detailed` reports `model_loaded` from singleton `get_model_loader().is_loaded` (true after first successful load).

---

## 8. Reports and training metadata

| Path | Content |
|------|---------|
| `reports/training_report.json` | Generic training output |
| `reports/cicids2017_training_report.json` | CICIDS training metrics |
| `reports/cicids2017_preprocess_report.json` | Preprocess stats |

---

## 9. Configuration (ML-related)

From `backend/config.py` / `.env.example`:

| Variable | Default |
|----------|---------|
| `MODEL_DIR` | `./backend/models` |
| `RF_MODEL_PATH` | `./backend/models/random_forest.pkl` |
| `XGB_MODEL_PATH` | `./backend/models/xgboost.pkl` |
| `LSTM_MODEL_PATH` | `./backend/models/lstm.h5` |
| `ENSEMBLE_MODEL_PATH` | `./backend/models/ensemble.pkl` |
| `MIN_PACKETS` | 10 |
| `PREDICTION_MODE` | once |
| `ALERT_THRESHOLD_CRITICAL` | 0.9 |
| `ALERT_THRESHOLD_HIGH` | 0.7 |
| `ALERT_THRESHOLD_MEDIUM` | 0.5 |

Note: `Predictor._determine_severity` uses hardcoded 0.9/0.8/0.75 thresholds; settings `ALERT_THRESHOLD_*` are **not wired** into Predictor in current code.

---

## 10. Verification commands

```bash
# Feature contract
python backend/scripts/validate_features.py

# Predictor unit path
python backend/scripts/test_predictor.py

# Train dummy artifacts
python backend/ml/create_dummy_models.py
ls models/

# XAI (server must be running, model present)
curl -X POST http://localhost:8000/api/xai/explain \
  -H "Content-Type: application/json" \
  -d @fixtures/explain_request.json
```

---

## 11. Known limitations

1. Two prediction stacks: **ModelLoader+Predictor** (pipeline) vs **IDSModel** (legacy `/api/predictions`).
2. `ALERT_THRESHOLD_*` env vars not applied in `Predictor`.
3. No model hot-reload in pipeline without restart/stop-start sniffer.
4. `inference.py` import broken.
5. Prometheus `track_prediction` never called from pipeline.
6. Class labels depend on training-time `LabelEncoder` — must match production attack names used in correlation rules (`PortScan`, `DDoS`, etc.).
