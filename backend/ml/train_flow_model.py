"""
Training Pipeline for Flow-Based IDS Model
Trains a real ML model using dataset aligned with the 20-feature extractor
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# The incoming dataset must exactly match the feature contract.
# COLUMN_MAPPING is no longer used since preprocessing aligns the dataset.


class FlowModelTrainer:
    """Train flow-based IDS model"""
    
    def __init__(
        self,
        data_path: str,
        label_column: str = "Label",
        model_type: str = "rf",
        test_size: float = 0.2,
        random_state: int = 42
    ):
        """
        Initialize trainer
        
        Args:
            data_path: Path to training dataset CSV
            label_column: Name of label column
            model_type: Model type (rf, xgb, ensemble)
            test_size: Test set proportion
            random_state: Random seed
        """
        self.data_path = Path(data_path)
        self.label_column = label_column
        self.model_type = model_type
        self.test_size = test_size
        self.random_state = random_state
        
        # Load feature contract
        self.feature_contract_path = Path(__file__).parent.parent.parent / "models" / "features.json"
        self.feature_names = self._load_feature_contract()
        
        # Model and preprocessing objects
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        
        # Training data
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        
        # Results
        self.metrics = {}
        self.training_report = {}
        
    def _load_feature_contract(self) -> list:
        """Load feature names from features.json"""
        try:
            with open(self.feature_contract_path, 'r') as f:
                contract = json.load(f)
            feature_names = contract['feature_names']
            logger.info(f"Loaded feature contract with {len(feature_names)} features")
            return feature_names
        except Exception as e:
            logger.error(f"Failed to load feature contract: {e}")
            raise
    
    def load_data(self) -> pd.DataFrame:
        """Load and preprocess dataset"""
        logger.info(f"Loading dataset from {self.data_path}")
        
        if not self.data_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.data_path}")
        
        df = pd.read_csv(self.data_path)
        logger.info(f"Loaded dataset with shape {df.shape}")
        
        # Check for label column
        if self.label_column not in df.columns:
            raise ValueError(f"Label column '{self.label_column}' not found in dataset")
        
        logger.info(f"Label distribution:\n{df[self.label_column].value_counts()}")
        
        return df
    
    def map_and_select_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Select exactly the features defined in the feature contract.
        Enforces: correct names, correct order, no missing columns.
        """
        logger.info("Verifying and selecting strict features from contract...")

        missing_features = [f for f in self.feature_names if f not in df.columns]
        if missing_features:
            raise ValueError(
                f"Dataset is missing required features: {missing_features}. "
                "Run preprocessing script first to align features."
            )

        extra_features = [c for c in df.columns if c not in self.feature_names and c != self.label_column]
        if extra_features:
            logger.warning(f"Dataset has extra columns (will be ignored): {extra_features}")

        feature_df = df[self.feature_names].copy()

        # Strict order assertion
        assert list(feature_df.columns) == self.feature_names, (
            f"Feature column order mismatch after selection: {list(feature_df.columns)}"
        )
        assert feature_df.shape[1] == len(self.feature_names), (
            f"Expected {len(self.feature_names)} feature columns, got {feature_df.shape[1]}"
        )

        logger.info(f"Feature contract verified: {feature_df.shape[1]} features in correct order.")
        return feature_df
    
    def preprocess_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Preprocess data: handle NaN/inf, ensure numeric dtype
        
        Args:
            df: Input dataframe
            
        Returns:
            X (features), y (labels)
        """
        logger.info("Preprocessing data...")
        
        # Extract labels
        y = df[self.label_column].values
        
        # Map and select features
        X_df = self.map_and_select_features(df)
        
        # Handle NaN and inf
        X_df = X_df.replace([np.inf, -np.inf], np.nan)
        X_df = X_df.fillna(0)
        
        # Ensure numeric dtype
        X = X_df.astype(np.float64).values
        
        logger.info(f"Feature matrix shape: {X.shape}")
        logger.info(f"Label array shape: {y.shape}")
        
        return X, y
    
    def split_data(self, X: np.ndarray, y: np.ndarray):
        """
        Stratified train/test split
        
        Args:
            X: Feature matrix
            y: Label array
        """
        logger.info(f"Splitting data with test_size={self.test_size}...")
        
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X, y,
            test_size=self.test_size,
            random_state=self.random_state,
            stratify=y
        )
        
        logger.info(f"Train set: {self.X_train.shape[0]} samples")
        logger.info(f"Test set: {self.X_test.shape[0]} samples")
        
        # Encode labels
        self.y_train_encoded = self.label_encoder.fit_transform(self.y_train)
        self.y_test_encoded = self.label_encoder.transform(self.y_test)
        
        logger.info(f"Classes: {list(self.label_encoder.classes_)}")
    
    def scale_features(self):
        """Apply StandardScaler to features"""
        logger.info("Scaling features...")
        
        self.X_train_scaled = self.scaler.fit_transform(self.X_train)
        self.X_test_scaled = self.scaler.transform(self.X_test)
        
        logger.info("Feature scaling complete")
    
    def train_model(self):
        """Train the model"""
        logger.info(f"Training {self.model_type} model...")
        
        if self.model_type == 'rf':
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=self.random_state,
                n_jobs=-1,
                class_weight='balanced'
            )
        elif self.model_type == 'xgb':
            try:
                import xgboost as xgb
                self.model = xgb.XGBClassifier(
                    n_estimators=100,
                    max_depth=6,
                    learning_rate=0.1,
                    random_state=self.random_state,
                    n_jobs=-1,
                    use_label_encoder=False,
                    eval_metric='logloss'
                )
            except ImportError:
                logger.warning("XGBoost not installed, falling back to RandomForest")
                self.model = RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    random_state=self.random_state,
                    n_jobs=-1,
                    class_weight='balanced'
                )
        elif self.model_type == 'ensemble':
            # Use RandomForest as ensemble base
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=self.random_state,
                n_jobs=-1,
                class_weight='balanced'
            )
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
        
        # Train
        self.model.fit(self.X_train_scaled, self.y_train_encoded)
        logger.info("Model training complete")
    
    def evaluate_model(self):
        """Evaluate model and compute metrics"""
        logger.info("Evaluating model...")
        
        # Predictions
        y_pred = self.model.predict(self.X_test_scaled)
        y_pred_proba = None
        
        if hasattr(self.model, 'predict_proba'):
            y_pred_proba = self.model.predict_proba(self.X_test_scaled)
        
        # Decode predictions
        y_pred_decoded = self.label_encoder.inverse_transform(y_pred)
        y_test_decoded = self.label_encoder.inverse_transform(self.y_test_encoded)
        
        # Metrics
        accuracy = accuracy_score(self.y_test_encoded, y_pred)
        precision = precision_score(self.y_test_encoded, y_pred, average='macro', zero_division=0)
        recall = recall_score(self.y_test_encoded, y_pred, average='macro', zero_division=0)
        f1 = f1_score(self.y_test_encoded, y_pred, average='macro', zero_division=0)
        
        # Confusion matrix
        cm = confusion_matrix(self.y_test_encoded, y_pred)
        
        # False Positive Rate for Normal class
        # FP = non-Normal samples predicted as Normal (column sum minus TP)
        # FPR = FP / (FP + TN) where TN = correct non-Normal predictions
        fpr = 0.0
        normal_idx = None
        for i, class_name in enumerate(self.label_encoder.classes_):
            if class_name.lower() == 'normal':
                normal_idx = i
                break

        if normal_idx is not None:
            tp = cm[normal_idx, normal_idx]
            # FP: other classes predicted as Normal
            fp = cm[:, normal_idx].sum() - tp
            # Total actual non-Normal samples
            total_non_normal = cm.sum() - cm[normal_idx, :].sum()
            if total_non_normal > 0:
                fpr = fp / total_non_normal
        
        # Per-class metrics
        per_class_precision = precision_score(self.y_test_encoded, y_pred, average=None, zero_division=0)
        per_class_recall = recall_score(self.y_test_encoded, y_pred, average=None, zero_division=0)
        per_class_f1 = f1_score(self.y_test_encoded, y_pred, average=None, zero_division=0)
        
        per_class_metrics = []
        for i, class_name in enumerate(self.label_encoder.classes_):
            per_class_metrics.append({
                'class': class_name,
                'precision': float(per_class_precision[i]),
                'recall': float(per_class_recall[i]),
                'f1': float(per_class_f1[i]),
                'support': int(cm[i, :].sum())
            })
        
        # Store metrics
        self.metrics = {
            'accuracy': float(accuracy),
            'precision_macro': float(precision),
            'recall_macro': float(recall),
            'f1_macro': float(f1),
            'confusion_matrix': cm.tolist(),
            'false_positive_rate': float(fpr),
            'class_names': list(self.label_encoder.classes_),
            'per_class_metrics': per_class_metrics
        }
        
        # Print metrics
        logger.info(f"\n{'='*60}")
        logger.info(f"EVALUATION METRICS")
        logger.info(f"{'='*60}")
        logger.info(f"Accuracy:          {accuracy:.4f}")
        logger.info(f"Precision (macro): {precision:.4f}")
        logger.info(f"Recall (macro):    {recall:.4f}")
        logger.info(f"F1 Score (macro):  {f1:.4f}")
        logger.info(f"FPR (Normal):      {fpr:.4f}")
        logger.info(f"\nConfusion Matrix:")
        logger.info(f"Classes: {self.label_encoder.classes_}")
        for row in cm:
            logger.info(f"  {row}")
        logger.info(f"\nClassification Report:")
        logger.info(f"\n{classification_report(y_test_decoded, y_pred_decoded)}")
        logger.info(f"{'='*60}\n")
    
    def save_artifacts(self, output_dir: str = "./models"):
        """
        Save model artifacts compatible with model_loader
        
        Args:
            output_dir: Directory to save artifacts
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Saving artifacts to {output_path}...")
        
        # Save model
        model_path = output_path / "ensemble.pkl"
        joblib.dump(self.model, model_path)
        logger.info(f"Saved model to {model_path}")
        
        # Save scaler
        scaler_path = output_path / "ensemble_scaler.pkl"
        joblib.dump(self.scaler, scaler_path)
        logger.info(f"Saved scaler to {scaler_path}")
        
        # Save label encoder
        encoder_path = output_path / "ensemble_encoder.pkl"
        joblib.dump(self.label_encoder, encoder_path)
        logger.info(f"Saved label encoder to {encoder_path}")
        
        # Rewrite features.json to ensure correct order
        features_path = output_path / "features.json"
        features_contract = {
            "feature_names": self.feature_names,
            "n_features": len(self.feature_names),
            "description": "Fixed feature order for ML model inference (must match feature_extractor.py)",
            "version": "1.0",
            "trained_with": self.model_type,
            "trained_date": datetime.now().isoformat()
        }
        with open(features_path, 'w') as f:
            json.dump(features_contract, f, indent=2)
        logger.info(f"Updated features.json at {features_path}")
    
    def save_training_report(self, output_dir: str = "./reports"):
        """
        Save training report to JSON
        
        Args:
            output_dir: Directory to save report
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        report_path = output_path / "cicids2017_training_report.json"
        
        self.training_report = {
            "training_date": datetime.now().isoformat(),
            "dataset_path": str(self.data_path),
            "dataset_shape": list(self.X_train.shape) if self.X_train is not None else None,
            "model_type": self.model_type,
            "n_features": len(self.feature_names),
            "feature_names": self.feature_names,
            "n_classes": len(self.label_encoder.classes_) if self.label_encoder.classes_ is not None else 0,
            "class_names": list(self.label_encoder.classes_) if self.label_encoder.classes_ is not None else [],
            "train_samples": int(self.X_train.shape[0]) if self.X_train is not None else 0,
            "test_samples": int(self.X_test.shape[0]) if self.X_test is not None else 0,
            "test_size": self.test_size,
            "random_state": self.random_state,
            # Top-level summary metrics
            "accuracy": self.metrics.get("accuracy"),
            "precision_macro": self.metrics.get("precision_macro"),
            "recall_macro": self.metrics.get("recall_macro"),
            "f1_macro": self.metrics.get("f1_macro"),
            "false_positive_rate": self.metrics.get("false_positive_rate"),
            "confusion_matrix": self.metrics.get("confusion_matrix"),
            "per_class_metrics": self.metrics.get("per_class_metrics"),
            # Full metrics block retained for compatibility
            "metrics": self.metrics,
            "model_params": self.model.get_params() if hasattr(self.model, 'get_params') else {}
        }
        
        with open(report_path, 'w') as f:
            json.dump(self.training_report, f, indent=2)
        
        logger.info(f"Saved training report to {report_path}")
    
    def run(self, output_dir: str = "./models"):
        """
        Run complete training pipeline
        
        Args:
            output_dir: Directory to save artifacts
        """
        logger.info("="*60)
        logger.info("STARTING TRAINING PIPELINE")
        logger.info("="*60)
        
        # Load data
        df = self.load_data()
        
        # Preprocess
        X, y = self.preprocess_data(df)
        
        # Split
        self.split_data(X, y)
        
        # Scale
        self.scale_features()
        
        # Train
        self.train_model()
        
        # Evaluate
        self.evaluate_model()
        
        # Save artifacts
        self.save_artifacts(output_dir)
        
        # Save report
        report_dir = Path(output_dir).parent / "reports"
        self.save_training_report(str(report_dir))
        
        logger.info("="*60)
        logger.info("TRAINING PIPELINE COMPLETE")
        logger.info("="*60)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Train flow-based IDS model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train with RandomForest
  python backend/ml/train_flow_model.py --data data/synthetic_traffic_data.csv --model rf
  
  # Train with XGBoost
  python backend/ml/train_flow_model.py --data data/synthetic_traffic_data.csv --model xgb
  
  # Train with ensemble
  python backend/ml/train_flow_model.py --data data/synthetic_traffic_data.csv --model ensemble
  
  # Custom label column
  python backend/ml/train_flow_model.py --data data/synthetic_traffic_data.csv --label_column Label
        """
    )
    
    parser.add_argument(
        '--data',
        type=str,
        required=True,
        help='Path to training dataset CSV file'
    )
    
    parser.add_argument(
        '--label',
        type=str,
        default='Label',
        help='Label column name (default: Label)'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        choices=['rf', 'xgb', 'ensemble'],
        default='rf',
        help='Model type: rf (RandomForest), xgb (XGBoost), ensemble (default: rf)'
    )
    
    parser.add_argument(
        '--test-size',
        type=float,
        default=0.2,
        help='Test set proportion (default: 0.2)'
    )
    
    parser.add_argument(
        '--random-state',
        type=int,
        default=42,
        help='Random seed (default: 42)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='./models',
        help='Output directory for artifacts (default: ./models)'
    )
    
    args = parser.parse_args()
    
    # Create trainer
    trainer = FlowModelTrainer(
        data_path=args.data,
        label_column=args.label,
        model_type=args.model,
        test_size=args.test_size,
        random_state=args.random_state
    )
    
    # Run training
    try:
        trainer.run(output_dir=args.output_dir)
        sys.exit(0)
    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
