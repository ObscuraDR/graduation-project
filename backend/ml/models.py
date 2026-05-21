"""
ML Models
Machine Learning model implementations for IDS
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import xgboost as xgb
import joblib
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional, Any

logger = logging.getLogger(__name__)


class IDSModel:
    """Base class for IDS ML models"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.is_trained = False
        self.feature_names = None
        
    def preprocess_data(self, X: pd.DataFrame, fit: bool = False) -> np.ndarray:
        """Preprocess features"""
        if fit:
            X_scaled = self.scaler.fit_transform(X)
        else:
            X_scaled = self.scaler.transform(X)
        return X_scaled
    
    def train(self, X_train: pd.DataFrame, y_train: pd.Series, 
              X_val: Optional[pd.DataFrame] = None, 
              y_val: Optional[pd.Series] = None) -> Dict[str, Any]:
        """Train the model"""
        raise NotImplementedError
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions"""
        if not self.is_trained:
            raise ValueError("Model is not trained yet")
        X_scaled = self.preprocess_data(X, fit=False)
        return self.model.predict(X_scaled)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get prediction probabilities"""
        if not self.is_trained:
            raise ValueError("Model is not trained yet")
        X_scaled = self.preprocess_data(X, fit=False)
        return self.model.predict_proba(X_scaled)
    
    def save(self, path: str):
        """Save model to disk"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'label_encoder': self.label_encoder,
            'feature_names': self.feature_names,
            'is_trained': self.is_trained
        }, path)
        logger.info(f"Model saved to {path}")
    
    def load(self, path: str):
        """Load model from disk"""
        data = joblib.load(path)
        self.model = data['model']
        self.scaler = data['scaler']
        self.label_encoder = data['label_encoder']
        self.feature_names = data['feature_names']
        self.is_trained = data['is_trained']
        logger.info(f"Model loaded from {path}")


class RandomForestIDS(IDSModel):
    """Random Forest model for IDS"""
    
    def __init__(self, n_estimators: int = 100, max_depth: int = 20, 
                 random_state: int = 42):
        super().__init__("RandomForest")
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
            n_jobs=-1,
            class_weight='balanced'
        )
    
    def train(self, X_train: pd.DataFrame, y_train: pd.Series,
              X_val: Optional[pd.DataFrame] = None,
              y_val: Optional[pd.Series] = None) -> Dict[str, Any]:
        """Train Random Forest model"""
        logger.info(f"Training {self.model_name}...")
        
        # Store feature names
        self.feature_names = X_train.columns.tolist()
        
        # Encode labels
        y_encoded = self.label_encoder.fit_transform(y_train)
        
        # Preprocess features
        X_scaled = self.preprocess_data(X_train, fit=True)
        
        # Train model
        self.model.fit(X_scaled, y_encoded)
        self.is_trained = True
        
        # Evaluate
        metrics = {}
        if X_val is not None and y_val is not None:
            y_val_encoded = self.label_encoder.transform(y_val)
            X_val_scaled = self.preprocess_data(X_val, fit=False)
            y_pred = self.model.predict(X_val_scaled)
            
            metrics['accuracy'] = float(self.model.score(X_val_scaled, y_val_encoded))
            metrics['classification_report'] = classification_report(
                y_val_encoded, y_pred, 
                target_names=self.label_encoder.classes_,
                output_dict=True
            )
            logger.info(f"Validation accuracy: {metrics['accuracy']:.4f}")
        
        logger.info(f"{self.model_name} training completed")
        return metrics


class XGBoostIDS(IDSModel):
    """XGBoost model for IDS"""
    
    def __init__(self, n_estimators: int = 200, max_depth: int = 10,
                 learning_rate: float = 0.1, random_state: int = 42):
        super().__init__("XGBoost")
        self.model = xgb.XGBClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            random_state=random_state,
            n_jobs=-1,
            eval_metric='mlogloss'
        )
    
    def train(self, X_train: pd.DataFrame, y_train: pd.Series,
              X_val: Optional[pd.DataFrame] = None,
              y_val: Optional[pd.Series] = None) -> Dict[str, Any]:
        """Train XGBoost model"""
        logger.info(f"Training {self.model_name}...")
        
        # Store feature names
        self.feature_names = X_train.columns.tolist()
        
        # Encode labels
        y_encoded = self.label_encoder.fit_transform(y_train)
        
        # Preprocess features
        X_scaled = self.preprocess_data(X_train, fit=True)
        
        # Train model
        self.model.fit(X_scaled, y_encoded)
        self.is_trained = True
        
        # Evaluate
        metrics = {}
        if X_val is not None and y_val is not None:
            y_val_encoded = self.label_encoder.transform(y_val)
            X_val_scaled = self.preprocess_data(X_val, fit=False)
            y_pred = self.model.predict(X_val_scaled)
            
            metrics['accuracy'] = float(self.model.score(X_val_scaled, y_val_encoded))
            metrics['classification_report'] = classification_report(
                y_val_encoded, y_pred,
                target_names=self.label_encoder.classes_,
                output_dict=True
            )
            logger.info(f"Validation accuracy: {metrics['accuracy']:.4f}")
        
        logger.info(f"{self.model_name} training completed")
        return metrics


class EnsembleIDS(IDSModel):
    """Ensemble model combining multiple classifiers"""
    
    def __init__(self, models: list = None, voting: str = 'soft'):
        super().__init__("Ensemble")
        self.models = models or []
        self.voting = voting
        self.ensemble = None
        
    def add_model(self, model: IDSModel, weight: float = 1.0):
        """Add a model to the ensemble"""
        self.models.append((model, weight))
        
    def train(self, X_train: pd.DataFrame, y_train: pd.Series,
              X_val: Optional[pd.DataFrame] = None,
              y_val: Optional[pd.Series] = None) -> Dict[str, Any]:
        """Train ensemble model"""
        logger.info(f"Training {self.model_name}...")
        
        # Train individual models
        estimators = []
        for model, weight in self.models:
            if not model.is_trained:
                model.train(X_train, y_train, X_val, y_val)
            estimators.append((model.model_name, model.model))
        
        # Create voting classifier
        self.ensemble = VotingClassifier(
            estimators=estimators,
            voting=self.voting
        )
        
        # Store feature names from first model
        self.feature_names = self.models[0][0].feature_names
        self.scaler = self.models[0][0].scaler
        self.label_encoder = self.models[0][0].label_encoder
        
        # Train ensemble
        y_encoded = self.label_encoder.transform(y_train)
        X_scaled = self.preprocess_data(X_train, fit=True)
        self.ensemble.fit(X_scaled, y_encoded)
        self.model = self.ensemble
        self.is_trained = True
        
        # Evaluate
        metrics = {}
        if X_val is not None and y_val is not None:
            y_val_encoded = self.label_encoder.transform(y_val)
            X_val_scaled = self.preprocess_data(X_val, fit=False)
            y_pred = self.ensemble.predict(X_val_scaled)
            
            metrics['accuracy'] = float(self.ensemble.score(X_val_scaled, y_val_encoded))
            metrics['classification_report'] = classification_report(
                y_val_encoded, y_pred,
                target_names=self.label_encoder.classes_,
                output_dict=True
            )
            logger.info(f"Validation accuracy: {metrics['accuracy']:.4f}")
        
        logger.info(f"{self.model_name} training completed")
        return metrics
