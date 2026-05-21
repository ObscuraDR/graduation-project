"""
LSTM Model for IDS
Deep learning model for sequential pattern detection
"""

import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class LSTMIDS:
    """LSTM model for IDS with sequential pattern detection"""
    
    def __init__(self, sequence_length: int = 10, num_features: int = None):
        self.model_name = "LSTM"
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.sequence_length = sequence_length
        self.num_features = num_features
        self.is_trained = False
        self.feature_names = None
        
    def create_sequences(self, X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create sequences for LSTM training
        
        Args:
            X: Feature array
            y: Label array
        
        Returns:
            Tuple of (X_sequences, y_sequences)
        """
        X_seq, y_seq = [], []
        
        for i in range(len(X) - self.sequence_length):
            X_seq.append(X[i:i + self.sequence_length])
            y_seq.append(y[i + self.sequence_length])
        
        return np.array(X_seq), np.array(y_seq)
    
    def build_model(self, num_classes: int):
        """Build LSTM model architecture"""
        self.model = keras.Sequential([
            layers.Input(shape=(self.sequence_length, self.num_features)),
            layers.LSTM(128, return_sequences=True),
            layers.Dropout(0.2),
            layers.LSTM(64, return_sequences=False),
            layers.Dropout(0.2),
            layers.Dense(32, activation='relu'),
            layers.Dropout(0.2),
            layers.Dense(num_classes, activation='softmax')
        ])
        
        self.model.compile(
            optimizer='adam',
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        logger.info(f"LSTM model built with {num_classes} classes")
    
    def preprocess_data(self, X: pd.DataFrame, fit: bool = False) -> np.ndarray:
        """Preprocess features"""
        if fit:
            X_scaled = self.scaler.fit_transform(X)
        else:
            X_scaled = self.scaler.transform(X)
        return X_scaled
    
    def train(self, X_train: pd.DataFrame, y_train: pd.Series,
              X_val: Optional[pd.DataFrame] = None,
              y_val: Optional[pd.Series] = None,
              epochs: int = 50,
              batch_size: int = 32) -> Dict[str, Any]:
        """Train LSTM model"""
        logger.info(f"Training {self.model_name}...")
        
        # Store feature names
        self.feature_names = X_train.columns.tolist()
        self.num_features = len(self.feature_names)
        
        # Encode labels
        y_encoded = self.label_encoder.fit_transform(y_train)
        num_classes = len(self.label_encoder.classes_)
        
        # Preprocess features
        X_scaled = self.preprocess_data(X_train, fit=True)
        
        # Create sequences
        X_seq, y_seq = self.create_sequences(X_scaled, y_encoded)
        logger.info(f"Created sequences: {X_seq.shape}")
        
        # Build model
        self.build_model(num_classes)
        
        # Prepare validation data
        validation_data = None
        if X_val is not None and y_val is not None:
            y_val_encoded = self.label_encoder.transform(y_val)
            X_val_scaled = self.preprocess_data(X_val, fit=False)
            X_val_seq, y_val_seq = self.create_sequences(X_val_scaled, y_val_encoded)
            validation_data = (X_val_seq, y_val_seq)
        
        # Train model
        history = self.model.fit(
            X_seq, y_seq,
            validation_data=validation_data,
            epochs=epochs,
            batch_size=batch_size,
            verbose=1
        )
        
        self.is_trained = True
        
        # Evaluate
        metrics = {}
        if validation_data is not None:
            y_pred = self.model.predict(X_val_seq)
            y_pred_classes = np.argmax(y_pred, axis=1)
            
            metrics['accuracy'] = float(history.history['val_accuracy'][-1])
            metrics['classification_report'] = classification_report(
                y_val_seq, y_pred_classes,
                target_names=self.label_encoder.classes_,
                output_dict=True
            )
            logger.info(f"Validation accuracy: {metrics['accuracy']:.4f}")
        
        logger.info(f"{self.model_name} training completed")
        return metrics
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions"""
        if not self.is_trained:
            raise ValueError("Model is not trained yet")
        
        X_scaled = self.preprocess_data(X, fit=False)
        
        # For single prediction, pad with previous data
        if len(X) < self.sequence_length:
            # Pad with zeros
            padding = np.zeros((self.sequence_length - len(X), self.num_features))
            X_padded = np.vstack([padding, X_scaled])
            X_padded = X_padded.reshape(1, self.sequence_length, self.num_features)
        else:
            # Take last sequence_length samples
            X_padded = X_scaled[-self.sequence_length:].reshape(1, self.sequence_length, self.num_features)
        
        predictions = self.model.predict(X_padded, verbose=0)
        predicted_classes = np.argmax(predictions, axis=1)
        
        return predicted_classes
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get prediction probabilities"""
        if not self.is_trained:
            raise ValueError("Model is not trained yet")
        
        X_scaled = self.preprocess_data(X, fit=False)
        
        if len(X) < self.sequence_length:
            padding = np.zeros((self.sequence_length - len(X), self.num_features))
            X_padded = np.vstack([padding, X_scaled])
            X_padded = X_padded.reshape(1, self.sequence_length, self.num_features)
        else:
            X_padded = X_scaled[-self.sequence_length:].reshape(1, self.sequence_length, self.num_features)
        
        return self.model.predict(X_padded, verbose=0)
    
    def save(self, path: str):
        """Save model to disk"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save Keras model
        model_path = path.replace('.pkl', '.h5')
        self.model.save(model_path)
        
        # Save preprocessing objects
        joblib.dump({
            'scaler': self.scaler,
            'label_encoder': self.label_encoder,
            'feature_names': self.feature_names,
            'is_trained': self.is_trained,
            'sequence_length': self.sequence_length,
            'num_features': self.num_features
        }, path)
        
        logger.info(f"LSTM model saved to {model_path} and {path}")
    
    def load(self, path: str):
        """Load model from disk"""
        # Load preprocessing objects
        data = joblib.load(path)
        self.scaler = data['scaler']
        self.label_encoder = data['label_encoder']
        self.feature_names = data['feature_names']
        self.is_trained = data['is_trained']
        self.sequence_length = data['sequence_length']
        self.num_features = data['num_features']
        
        # Load Keras model
        model_path = path.replace('.pkl', '.h5')
        self.model = keras.models.load_model(model_path)
        
        logger.info(f"LSTM model loaded from {model_path} and {path}")
