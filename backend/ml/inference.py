"""
Model Inference Pipeline
Load models and make predictions on real-time features
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import logging
from pathlib import Path

from backend.ml.models import RandomForestIDS, XGBoostIDS, EnsembleIDS
from backend.config import settings
from backend.alerts.engine import AlertEngine

logger = logging.getLogger(__name__)


class InferencePipeline:
    """Pipeline for real-time inference"""
    
    def __init__(self):
        self.model: Optional[IDSModel] = None
        self.alert_engine = AlertEngine()
        self.model_loaded = False
        
    def load_model(self, model_path: str, model_type: str = "ensemble"):
        """Load trained model"""
        try:
            logger.info(f"Loading model from {model_path}")
            
            if model_type == "random_forest":
                self.model = RandomForestIDS()
            elif model_type == "xgboost":
                self.model = XGBoostIDS()
            elif model_type == "ensemble":
                self.model = EnsembleIDS()
            else:
                raise ValueError(f"Unsupported model type: {model_type}")
            
            self.model.load(model_path)
            self.model_loaded = True
            logger.info(f"Model loaded successfully: {model_type}")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
    
    def load_default_model(self):
        """Load default model from settings"""
        if Path(settings.ensemble_model_path).exists():
            self.load_model(settings.ensemble_model_path, "ensemble")
        elif Path(settings.xgb_model_path).exists():
            self.load_model(settings.xgb_model_path, "xgboost")
        elif Path(settings.rf_model_path).exists():
            self.load_model(settings.rf_model_path, "random_forest")
        else:
            logger.warning("No trained model found")
    
    def predict_single(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make prediction on single feature set
        
        Args:
            features: Dictionary of feature names and values
        
        Returns:
            Prediction result with class and confidence
        """
        if not self.model_loaded:
            raise ValueError("Model not loaded")
        
        try:
            # Convert to DataFrame
            feature_df = pd.DataFrame([features])
            
            # Ensure feature order matches training
            if self.model.feature_names:
                # Reorder and add missing features
                for feat in self.model.feature_names:
                    if feat not in feature_df.columns:
                        feature_df[feat] = 0
                feature_df = feature_df[self.model.feature_names]
            
            # Make prediction
            prediction = self.model.predict(feature_df)
            prediction_proba = self.model.predict_proba(feature_df)
            
            # Get predicted class and confidence
            predicted_class = self.model.label_encoder.inverse_transform([prediction[0]])[0]
            confidence = float(prediction_proba[0][prediction[0]])
            
            result = {
                "class": predicted_class,
                "confidence": confidence,
                "model_name": self.model.model_name,
                "model_version": "1.0",
                "all_probabilities": {
                    self.model.label_encoder.inverse_transform([i])[0]: float(prob)
                    for i, prob in enumerate(prediction_proba[0])
                }
            }
            
            logger.debug(f"Prediction: {predicted_class} (confidence: {confidence:.4f})")
            return result
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            raise
    
    def predict_batch(self, features_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Make predictions on batch of features
        
        Args:
            features_list: List of feature dictionaries
        
        Returns:
            List of prediction results
        """
        if not self.model_loaded:
            raise ValueError("Model not loaded")
        
        try:
            # Convert to DataFrame
            feature_df = pd.DataFrame(features_list)
            
            # Ensure feature order matches training
            if self.model.feature_names:
                for feat in self.model.feature_names:
                    if feat not in feature_df.columns:
                        feature_df[feat] = 0
                feature_df = feature_df[self.model.feature_names]
            
            # Make predictions
            predictions = self.model.predict(feature_df)
            prediction_proba = self.model.predict_proba(feature_df)
            
            results = []
            for i, (pred, proba) in enumerate(zip(predictions, prediction_proba)):
                predicted_class = self.model.label_encoder.inverse_transform([pred])[0]
                confidence = float(proba[pred])
                
                results.append({
                    "class": predicted_class,
                    "confidence": confidence,
                    "model_name": self.model.model_name,
                    "model_version": "1.0"
                })
            
            logger.info(f"Batch prediction completed: {len(results)} samples")
            return results
            
        except Exception as e:
            logger.error(f"Batch prediction error: {e}")
            raise
    
    def predict_and_alert(self, features: Dict[str, Any], 
                         packet_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Make prediction and generate alert if attack detected
        
        Args:
            features: Feature dictionary
            packet_info: Packet information (source_ip, dest_ip, ports, etc.)
        
        Returns:
            Alert if attack detected, None otherwise
        """
        # Make prediction
        prediction = self.predict_single(features)
        
        # Generate alert if attack
        alert = self.alert_engine.generate_alert(prediction, packet_info)
        
        if alert:
            logger.info(f"Alert generated: {alert['attack_type']} from {alert['source_ip']}")
        
        return alert
    
    def predict_batch_and_alert(self, features_list: List[Dict[str, Any]],
                                packet_infos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Make batch predictions and generate alerts
        
        Args:
            features_list: List of feature dictionaries
            packet_infos: List of packet information dictionaries
        
        Returns:
            List of generated alerts
        """
        # Make predictions
        predictions = self.predict_batch(features_list)
        
        # Generate alerts
        alerts = self.alert_engine.batch_generate_alerts(predictions, packet_infos)
        
        if alerts:
            logger.info(f"Generated {len(alerts)} alerts from batch")
        
        return alerts
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded model"""
        if not self.model_loaded:
            return {"loaded": False}
        
        return {
            "loaded": True,
            "model_name": self.model.model_name,
            "is_trained": self.model.is_trained,
            "feature_count": len(self.model.feature_names) if self.model.feature_names else 0,
            "feature_names": self.model.feature_names
        }


# Global inference pipeline instance
inference_pipeline = InferencePipeline()
