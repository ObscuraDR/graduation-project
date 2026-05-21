"""
Model Training Script
Train ML models on CICIDS2017 dataset
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
import argparse
from datetime import datetime

from backend.ml.models import RandomForestIDS, XGBoostIDS, EnsembleIDS
try:
    from backend.ml.lstm_model import LSTMIDS
    LSTM_AVAILABLE = True
except ImportError:
    LSTM_AVAILABLE = False
    logger.warning("LSTM not available (TensorFlow not installed)")
from backend.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_data(data_path: str) -> pd.DataFrame:
    """Load dataset from CSV file"""
    logger.info(f"Loading data from {data_path}")
    df = pd.read_csv(data_path)
    logger.info(f"Loaded {len(df)} samples with {len(df.columns)} features")
    return df


def preprocess_data(df: pd.DataFrame) -> tuple:
    """Preprocess data for training"""
    logger.info("Preprocessing data...")
    
    # Drop non-feature columns
    label_col = 'Label' if 'Label' in df.columns else 'label'
    
    # Handle missing values
    df = df.dropna()
    
    # Separate features and labels
    if label_col in df.columns:
        X = df.drop(columns=[label_col])
        y = df[label_col]
    else:
        raise ValueError(f"Label column '{label_col}' not found in dataset")
    
    # Drop non-numeric columns
    X = X.select_dtypes(include=[np.number])
    
    # Drop columns with all zeros or constant values
    X = X.loc[:, (X != 0).any()]
    X = X.loc[:, X.nunique() > 1]
    
    logger.info(f"Features after preprocessing: {X.shape[1]}")
    logger.info(f"Classes: {y.unique()}")
    logger.info(f"Class distribution:\n{y.value_counts()}")
    
    return X, y


def train_random_forest(X_train, y_train, X_val, y_val, save_path: str):
    """Train Random Forest model"""
    logger.info("Training Random Forest model...")
    
    model = RandomForestIDS(n_estimators=100, max_depth=20)
    metrics = model.train(X_train, y_train, X_val, y_val)
    
    model.save(save_path)
    logger.info(f"Random Forest model saved to {save_path}")
    
    return model, metrics


def train_xgboost(X_train, y_train, X_val, y_val, save_path: str):
    """Train XGBoost model"""
    logger.info("Training XGBoost model...")
    
    model = XGBoostIDS(n_estimators=200, max_depth=10, learning_rate=0.1)
    metrics = model.train(X_train, y_train, X_val, y_val)
    
    model.save(save_path)
    logger.info(f"XGBoost model saved to {save_path}")
    
    return model, metrics


def train_lstm(X_train, y_train, X_val, y_val, save_path: str, epochs: int = 50):
    """Train LSTM model"""
    if not LSTM_AVAILABLE:
        logger.warning("LSTM training skipped (TensorFlow not installed)")
        return None, {}
    
    logger.info("Training LSTM model...")
    
    model = LSTMIDS(sequence_length=10)
    metrics = model.train(X_train, y_train, X_val, y_val, epochs=epochs)
    
    model.save(save_path)
    logger.info(f"LSTM model saved to {save_path}")
    
    return model, metrics


def train_ensemble(X_train, y_train, X_val, y_val, save_path: str):
    """Train Ensemble model"""
    logger.info("Training Ensemble model...")
    
    # Train individual models
    rf_model, _ = train_random_forest(X_train, y_train, X_val, y_val, 
                                      settings.rf_model_path)
    xgb_model, _ = train_xgboost(X_train, y_train, X_val, y_val,
                                  settings.xgb_model_path)
    
    # Create ensemble
    ensemble = EnsembleIDS(voting='soft')
    ensemble.add_model(rf_model, weight=0.5)
    ensemble.add_model(xgb_model, weight=0.5)
    
    metrics = ensemble.train(X_train, y_train, X_val, y_val)
    ensemble.save(save_path)
    logger.info(f"Ensemble model saved to {save_path}")
    
    return ensemble, metrics


def save_model_metadata(model, metrics, model_name: str, version: str):
    """Save model metadata to database"""
    from backend.database.connection import SessionLocal
    from backend.database.models import Model as DBModel
    
    db = SessionLocal()
    try:
        # Get metrics from classification report
        report = metrics.get('classification_report', {})
        accuracy = metrics.get('accuracy', 0.0)
        
        # Get weighted average metrics
        weighted_avg = report.get('weighted avg', {})
        precision = weighted_avg.get('precision', 0.0)
        recall = weighted_avg.get('recall', 0.0)
        f1_score = weighted_avg.get('f1-score', 0.0)
        
        # Determine algorithm
        algorithm = model.model_name
        
        # Create model record
        db_model = DBModel(
            model_name=model_name,
            version=version,
            algorithm=algorithm,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            file_path=getattr(settings, f"{algorithm.lower()}_model_path", ""),
            is_active=True
        )
        
        db.add(db_model)
        db.commit()
        
        logger.info(f"Model metadata saved to database")
    
    except Exception as e:
        logger.error(f"Error saving model metadata: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Train IDS ML models")
    parser.add_argument("--data", type=str, required=True, help="Path to training data CSV")
    parser.add_argument("--model", type=str, default="ensemble", 
                       choices=["rf", "xgb", "lstm", "ensemble"], help="Model to train")
    parser.add_argument("--version", type=str, default="1.0", help="Model version")
    parser.add_argument("--epochs", type=int, default=50, help="Number of epochs for LSTM")
    args = parser.parse_args()
    
    # Create model directory
    Path(settings.model_dir).mkdir(parents=True, exist_ok=True)
    
    # Load and preprocess data
    df = load_data(args.data)
    X, y = preprocess_data(df)
    
    # Split data
    from sklearn.model_selection import train_test_split
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
    )
    
    logger.info(f"Train set: {X_train.shape}")
    logger.info(f"Validation set: {X_val.shape}")
    logger.info(f"Test set: {X_test.shape}")
    
    # Train model
    if args.model == "rf":
        model, metrics = train_random_forest(
            X_train, y_train, X_val, y_val, settings.rf_model_path
        )
        save_model_metadata(model, metrics, "Random Forest", args.version)
    
    elif args.model == "xgb":
        model, metrics = train_xgboost(
            X_train, y_train, X_val, y_val, settings.xgb_model_path
        )
        save_model_metadata(model, metrics, "XGBoost", args.version)
    
    elif args.model == "lstm":
        model, metrics = train_lstm(
            X_train, y_train, X_val, y_val, settings.lstm_model_path, args.epochs
        )
        save_model_metadata(model, metrics, "LSTM", args.version)
    
    elif args.model == "ensemble":
        model, metrics = train_ensemble(
            X_train, y_train, X_val, y_val, settings.ensemble_model_path
        )
        save_model_metadata(model, metrics, "Ensemble", args.version)
    
    logger.info("Training completed successfully")


if __name__ == "__main__":
    main()
