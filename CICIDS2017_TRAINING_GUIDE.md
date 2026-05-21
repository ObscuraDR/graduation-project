# CICIDS2017 Training Guide

This guide provides step-by-step instructions to train real ML models from CICIDS2017 dataset for the IDS backend.

## Prerequisites

1. **CICIDS2017 Dataset**: Download the CICIDS2017 dataset from the official source and extract CSV files to a directory.
2. **Python Dependencies**: Ensure all required packages are installed:
   ```bash
   pip install pandas numpy scikit-learn joblib xgboost
   ```

## Quick Start (Windows PowerShell)

Run the automated training pipeline:

```powershell
# Navigate to project directory
cd "d:\graduation project"

# Run the automation script
.\scripts\train_cicids2017.ps1 -InputDir "path\to\cicids2017\csv\files" -ModelType "rf"
```

### Parameters

- `-InputDir` (required): Directory containing CICIDS2017 CSV files
- `-OutputCsv` (optional): Output path for processed CSV (default: `data/cicids2017_processed.csv`)
- `-ModelType` (optional): Model type - `rf` (RandomForest), `xgb` (XGBoost), or `ensemble` (default: `rf`)
- `-OutputDir` (optional): Output directory for model artifacts (default: `models`)
- `-TestSize` (optional): Test set proportion (default: 0.2)

## Manual Training Steps

### Step 1: Preprocess CICIDS2017 Dataset

```bash
python scripts/preprocess_cicids2017.py --input-dir "path/to/cicids2017/csv/files" --output data/cicids2017_processed.csv
```

**Expected Output:**
- Creates `data/cicids2017_processed.csv` with exactly 20 feature columns + Label
- Creates `reports/cicids2017_preprocess_report.json` with preprocessing statistics

**Verification:**
```bash
# Check CSV structure
python -c "import pandas as pd; df = pd.read_csv('data/cicids2017_processed.csv'); print('Columns:', df.columns.tolist()); print('Shape:', df.shape)"
```

**Expected Output:**
```
Columns: ['flow_duration', 'total_fwd_packets', 'total_bwd_packets', 'total_fwd_bytes', 
          'total_bwd_bytes', 'avg_packet_size', 'packet_rate', 'byte_rate', 'syn_count', 
          'fin_count', 'rst_count', 'psh_count', 'ack_count', 'unique_dst_ports', 
          'inter_arrival_time_mean', 'fwd_packet_rate', 'bwd_packet_rate', 'fwd_byte_rate', 
          'bwd_byte_rate', 'packet_length_mean', 'Label']
Shape: (N, 21)  # N depends on dataset size
```

### Step 2: Train ML Model

```bash
python backend/ml/train_flow_model.py --data data/cicids2017_processed.csv --model rf --output-dir models
```

**Expected Output:**
- Creates `models/ensemble.pkl` - Trained model
- Creates `models/ensemble_scaler.pkl` - Feature scaler
- Creates `models/ensemble_encoder.pkl` - Label encoder
- Updates `models/features.json` - Feature contract
- Creates `reports/cicids2017_training_report.json` - Training metrics

**Training Console Output:**
```
============================================================
STARTING TRAINING PIPELINE
============================================================
Loading dataset from data/cicids2017_processed.csv
Loaded dataset with shape (N, 21)
Label distribution:
Normal: XXXX
DDoS: XXXX
PortScan: XXXX
...
Verifying and selecting strict features from contract...
Selected strict feature dataframe with shape (N, 20)
Preprocessing data...
Feature matrix shape: (N, 20)
Label array shape: (N,)
Splitting data with test_size=0.2...
Train set: XXXX samples
Test set: XXXX samples
Classes: ['Normal', 'DDoS', 'PortScan', ...]
Scaling features...
Feature scaling complete
Training rf model...
Model training complete
Evaluating model...

============================================================
EVALUATION METRICS
============================================================
Accuracy:          0.XXXX
Precision (macro): 0.XXXX
Recall (macro):    0.XXXX
F1 Score (macro):  0.XXXX
FPR (Normal):      0.XXXX

Confusion Matrix:
Classes: ['Normal', 'DDoS', 'PortScan', ...]
  [row1]
  [row2]
  ...

Classification Report:
              precision    recall  f1-score   support
...
============================================================

Saving artifacts to models...
Saved model to models/ensemble.pkl
Saved scaler to models/ensemble_scaler.pkl
Saved label encoder to models/ensemble_encoder.pkl
Updated features.json at models/features.json
Saved training report to reports/cicids2017_training_report.json
============================================================
TRAINING PIPELINE COMPLETE
============================================================
```

### Step 3: Verify Model Loading

```bash
python -c "
from backend.detection_engine.model_loader import get_model_loader
import json

# Load model
loader = get_model_loader('models')
success = loader.load_from_directory('ensemble')

if success:
    info = loader.get_model_info()
    print('Model loaded successfully!')
    print(f'Model type: {info[\"model_type\"]}')
    print(f'Features: {info[\"n_features\"]}')
    print(f'Classes: {info[\"class_names\"]}')
    
    # Load training report
    with open('reports/cicids2017_training_report.json', 'r') as f:
        report = json.load(f)
    print(f'\nTraining accuracy: {report[\"metrics\"][\"accuracy\"]:.4f}')
    print(f'FPR (Normal): {report[\"metrics\"][\"false_positive_rate\"]:.4f}')
else:
    print('Failed to load model')
"
```

**Expected Output:**
```
Model loaded successfully!
Model type: sklearn
Features: 20
Classes: ['Normal', 'DDoS', 'PortScan', 'BruteForce', 'Botnet', 'Abnormal']

Training accuracy: 0.XXXX
FPR (Normal): 0.XXXX
```

### Step 4: Test Inference

```bash
python -c "
from backend.detection_engine.model_loader import get_model_loader
import numpy as np

# Load model
loader = get_model_loader('models')
loader.load_from_directory('ensemble')

# Create sample features (20 features)
sample_features = np.array([[1.0, 10, 5, 1000, 500, 100, 10, 1000, 1, 0, 0, 1, 8, 1, 0.1, 5, 5, 500, 500, 100]])

# Predict
prediction = loader.predict(sample_features)
class_names = loader.get_class_names()
predicted_class = class_names[prediction[0]]

print(f'Predicted class: {predicted_class}')

# Get probabilities
proba = loader.predict_proba(sample_features)
print(f'Class probabilities:')
for i, cls in enumerate(class_names):
    print(f'  {cls}: {proba[0][i]:.4f}')
"
```

**Expected Output:**
```
Predicted class: Normal
Class probabilities:
  Normal: 0.XXXX
  DDoS: 0.XXXX
  PortScan: 0.XXXX
  BruteForce: 0.XXXX
  Botnet: 0.XXXX
  Abnormal: 0.XXXX
```

## Training Report Structure

The training report (`reports/cicids2017_training_report.json`) contains:

```json
{
  "training_date": "ISO timestamp",
  "dataset_path": "data/cicids2017_processed.csv",
  "dataset_shape": [N, 21],
  "model_type": "rf",
  "n_features": 20,
  "feature_names": ["flow_duration", ...],
  "n_classes": 6,
  "class_names": ["Normal", "DDoS", "PortScan", "BruteForce", "Botnet", "Abnormal"],
  "train_samples": N_train,
  "test_samples": N_test,
  "test_size": 0.2,
  "random_state": 42,
  "metrics": {
    "accuracy": 0.XXXX,
    "precision_macro": 0.XXXX,
    "recall_macro": 0.XXXX,
    "f1_macro": 0.XXXX,
    "confusion_matrix": [[...], [...], ...],
    "false_positive_rate": 0.XXXX,
    "class_names": [...],
    "per_class_metrics": [
      {
        "class": "Normal",
        "precision": 0.XXXX,
        "recall": 0.XXXX,
        "f1": 0.XXXX,
        "support": N
      },
      ...
    ]
  },
  "model_params": {...}
}
```

## Model Artifacts

After training, the following artifacts are created in `models/`:

1. **ensemble.pkl** - Trained RandomForest model
2. **ensemble_scaler.pkl** - StandardScaler for feature normalization
3. **ensemble_encoder.pkl** - LabelEncoder for class mapping
4. **features.json** - Feature contract with 20 features

## Troubleshooting

### Issue: Preprocessing fails with "No CSV files found"
**Solution:** Ensure the input directory path is correct and contains CSV files.

### Issue: Training fails with "Dataset is missing required features"
**Solution:** Ensure preprocessing completed successfully and the output CSV has all 20 features.

### Issue: Model loading fails with warnings
**Solution:** Verify all artifacts exist in the models directory and are compatible.

### Issue: Low accuracy or high FPR
**Solution:** 
- Check dataset quality and class distribution
- Try different model types (xgb instead of rf)
- Adjust model hyperparameters in train_flow_model.py

## Integration with Backend

Once trained, the models are automatically used by the backend:

1. The `model_loader.py` loads artifacts from `models/` directory
2. The detection engine uses the loaded model for inference
3. No code changes required - the backend will use the real trained models

## Next Steps

After training:

1. Review the training report to assess model performance
2. Test the model with sample traffic data
3. Monitor FPR (False Positive Rate) for Normal class
4. If performance is unsatisfactory, consider:
   - Collecting more training data
   - Adjusting class weights
   - Trying different model architectures
   - Feature engineering
