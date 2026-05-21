"""
Model Loader
Load ML model artifacts (.pkl, .joblib, .h5) with scaler and label encoder
"""

import logging
import joblib
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)


class ModelLoader:
    """Load and manage ML model artifacts"""
    
    def __init__(self, model_dir: str = "./models"):
        """
        Initialize model loader
        
        Args:
            model_dir: Directory containing model artifacts
        """
        self.model_dir = Path(model_dir)
        self.model = None
        self.scaler = None
        self.label_encoder = None
        self.feature_names = None
        self.model_type = None
        self.is_loaded = False
        
    def load_model(
        self,
        model_path: str,
        scaler_path: Optional[str] = None,
        label_encoder_path: Optional[str] = None
    ) -> bool:
        """
        Load model artifacts
        
        Args:
            model_path: Path to model file (.pkl, .joblib, .h5)
            scaler_path: Path to scaler file (optional)
            label_encoder_path: Path to label encoder file (optional)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            model_path = Path(model_path)
            
            if not model_path.exists():
                logger.error(f"Model file not found: {model_path}")
                return False
            
            # Determine model type and load accordingly
            if model_path.suffix == '.h5':
                # TensorFlow/Keras model
                try:
                    import tensorflow as tf
                    self.model = tf.keras.models.load_model(str(model_path))
                    self.model_type = 'tensorflow'
                    logger.info(f"Loaded TensorFlow model from {model_path}")
                except ImportError:
                    logger.error("TensorFlow not installed, cannot load .h5 model")
                    return False
            else:
                # Scikit-learn/XGBoost model
                self.model = joblib.load(model_path)
                self.model_type = 'sklearn'
                logger.info(f"Loaded sklearn model from {model_path}")
            
            # Load scaler if provided
            if scaler_path:
                scaler_path = Path(scaler_path)
                if scaler_path.exists():
                    self.scaler = joblib.load(scaler_path)
                    logger.info(f"Loaded scaler from {scaler_path}")
                else:
                    logger.warning(f"Scaler file not found: {scaler_path}")
            
            # Load label encoder if provided
            if label_encoder_path:
                label_encoder_path = Path(label_encoder_path)
                if label_encoder_path.exists():
                    self.label_encoder = joblib.load(label_encoder_path)
                    logger.info(f"Loaded label encoder from {label_encoder_path}")
                else:
                    logger.warning(f"Label encoder file not found: {label_encoder_path}")
            
            # Try to load feature names from model if available
            if hasattr(self.model, 'feature_names_in_'):
                self.feature_names = list(self.model.feature_names_in_)
                logger.info(f"Extracted feature names from model: {len(self.feature_names)} features")
            
            self.is_loaded = True
            logger.info("Model artifacts loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False
    
    def load_from_directory(self, model_name: str = "ensemble") -> bool:
        """
        Load model artifacts from model directory
        
        Args:
            model_name: Name of model (rf, xgb, lstm, ensemble)
        
        Returns:
            True if successful, False otherwise
        """
        model_path = self.model_dir / f"{model_name}.pkl"
        scaler_path = self.model_dir / f"{model_name}_scaler.pkl"
        label_encoder_path = self.model_dir / f"{model_name}_encoder.pkl"
        
        return self.load_model(model_path, scaler_path, label_encoder_path)
    
    def predict(self, features: np.ndarray) -> np.ndarray:
        """
        Make prediction using loaded model
        
        Args:
            features: Feature array (n_samples, n_features)
        
        Returns:
            Prediction array
        """
        if not self.is_loaded:
            raise ValueError("Model not loaded")
        
        # Apply scaler if available
        if self.scaler:
            features = self.scaler.transform(features)
        
        # Make prediction
        if self.model_type == 'tensorflow':
            predictions = self.model.predict(features, verbose=0)
            predicted_classes = np.argmax(predictions, axis=1)
        else:
            predicted_classes = self.model.predict(features)
        
        return predicted_classes
    
    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        """
        Get prediction probabilities
        
        Args:
            features: Feature array (n_samples, n_features)
        
        Returns:
            Probability array
        """
        if not self.is_loaded:
            raise ValueError("Model not loaded")
        
        # Apply scaler if available
        if self.scaler:
            features = self.scaler.transform(features)
        
        # Get probabilities
        if self.model_type == 'tensorflow':
            probabilities = self.model.predict(features, verbose=0)
        else:
            if hasattr(self.model, 'predict_proba'):
                probabilities = self.model.predict_proba(features)
            else:
                # Model doesn't support predict_proba, return binary
                predictions = self.model.predict(features)
                probabilities = np.zeros((len(predictions), 2))
                probabilities[:, 1] = predictions
                probabilities[:, 0] = 1 - predictions
        
        return probabilities
    
    def get_class_names(self) -> list:
        """
        Get class names from label encoder
        
        Returns:
            List of class names
        """
        if self.label_encoder:
            return list(self.label_encoder.classes_)
        return ['Normal', 'Attack']  # Default
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get model information
        
        Returns:
            Dictionary with model info
        """
        return {
            'is_loaded': self.is_loaded,
            'model_type': self.model_type,
            'feature_names': self.feature_names,
            'n_features': len(self.feature_names) if self.feature_names else 0,
            'n_classes': len(self.get_class_names()),
            'class_names': self.get_class_names()
        }


# Singleton instance
_model_loader_instance: Optional[ModelLoader] = None


def get_model_loader(model_dir: str = "./models") -> ModelLoader:
    """
    Get or create model loader instance
    
    Args:
        model_dir: Model directory
    
    Returns:
        ModelLoader instance
    """
    global _model_loader_instance
    
    if _model_loader_instance is None:
        _model_loader_instance = ModelLoader(model_dir=model_dir)
    
    return _model_loader_instance
