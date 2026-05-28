"""
Predictor
ML model inference pipeline for attack detection
"""

import logging
import numpy as np
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.detection_engine.model_loader import ModelLoader, get_model_loader
from backend.feature_engine.feature_extractor import FeatureExtractor, get_feature_extractor
from backend.flow_engine.flow_builder import Flow

logger = logging.getLogger(__name__)


class FeatureContractError(ValueError):
    """Raised when features.json and the live feature extractor are out of sync."""


class Predictor:
    """ML model predictor for attack detection"""
    
    def __init__(
        self,
        model_loader: Optional[ModelLoader] = None,
        feature_extractor: Optional[FeatureExtractor] = None,
        confidence_threshold: float = 0.75,
        features_path: str = "./backend/models/features.json"
    ):
        """
        Initialize predictor
        
        Args:
            model_loader: Model loader instance
            feature_extractor: Feature extractor instance
            confidence_threshold: Minimum confidence for attack detection
            features_path: Path to features.json for fixed feature order
        """
        self.model_loader = model_loader or get_model_loader()
        self.feature_extractor = feature_extractor or get_feature_extractor()
        self.confidence_threshold = confidence_threshold
        self.total_predictions = 0
        self.attack_predictions = 0
        
        # Load fixed feature order (must match feature_extractor.py)
        self.features_path = features_path
        self.feature_names = self._load_feature_order(features_path)
        self._validate_feature_contract()

    @staticmethod
    def validate_feature_contract(
        feature_names: List[str],
        extractor_names: List[str],
        n_features_declared: Optional[int] = None,
        source: str = "features.json",
    ) -> None:
        """
        Ensure features.json and FeatureExtractor define the same ordered feature list.

        Raises:
            FeatureContractError: On count or name/order mismatch.
        """
        if not feature_names:
            raise FeatureContractError(f"{source}: feature_names is empty")

        if n_features_declared is not None and n_features_declared != len(feature_names):
            raise FeatureContractError(
                f"{source}: n_features={n_features_declared} but feature_names has "
                f"{len(feature_names)} entries"
            )

        if len(feature_names) != len(extractor_names):
            raise FeatureContractError(
                f"Feature count mismatch: {source} defines {len(feature_names)} features, "
                f"feature_extractor.py defines {len(extractor_names)}"
            )

        for index, (json_name, extractor_name) in enumerate(
            zip(feature_names, extractor_names)
        ):
            if json_name != extractor_name:
                raise FeatureContractError(
                    f"Feature order mismatch at index {index}: "
                    f"{source} has '{json_name}', extractor has '{extractor_name}'"
                )

    def _validate_feature_contract(self) -> None:
        """Validate features.json against the live feature extractor."""
        extractor_names = self.feature_extractor.get_feature_names()
        n_features_declared = None

        features_file = Path(self.features_path)
        if features_file.exists():
            with open(features_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            n_features_declared = data.get("n_features")

        self.validate_feature_contract(
            self.feature_names,
            extractor_names,
            n_features_declared=n_features_declared,
            source=self.features_path,
        )

    def _load_feature_order(self, features_path: str) -> List[str]:
        """Load fixed feature order from JSON; fall back to extractor if file is missing."""
        features_file = Path(features_path)
        if not features_file.exists():
            logger.warning(
                f"Features file not found: {features_path}, using feature_extractor order"
            )
            return self.feature_extractor.get_feature_names()

        try:
            with open(features_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise FeatureContractError(
                f"Failed to load feature order from {features_path}: {e}"
            ) from e

        feature_names = data.get("feature_names")
        if not feature_names:
            raise FeatureContractError(
                f"{features_path}: missing or empty 'feature_names' array"
            )

        n_features = data.get("n_features")
        if n_features is not None and n_features != len(feature_names):
            raise FeatureContractError(
                f"{features_path}: n_features={n_features} but feature_names has "
                f"{len(feature_names)} entries"
            )

        return list(feature_names)

    def _validate_features(self, features: Dict[str, float]) -> np.ndarray:
        """
        Validate and clean features before inference.

        Args:
            features: Feature dictionary from FeatureExtractor.extract_features()

        Returns:
            Cleaned feature array in features.json order

        Raises:
            FeatureContractError: If required features are missing or counts differ.
        """
        expected = self.feature_names
        if len(features) != len(expected):
            raise FeatureContractError(
                f"Extractor returned {len(features)} features, expected {len(expected)}. "
                f"Keys: {sorted(features.keys())}"
            )

        missing = [name for name in expected if name not in features]
        if missing:
            raise FeatureContractError(
                f"Missing features for inference: {missing}"
            )

        feature_array = np.array([float(features[name]) for name in expected], dtype=np.float64)

        if len(feature_array) != len(expected):
            raise FeatureContractError(
                f"Feature vector length {len(feature_array)} != expected {len(expected)}"
            )

        # Replace NaN with 0
        feature_array = np.nan_to_num(feature_array, nan=0.0)

        # Replace +/- inf with finite bounds
        pos_inf = np.isposinf(feature_array)
        neg_inf = np.isneginf(feature_array)
        if pos_inf.any() or neg_inf.any():
            feature_array = feature_array.copy()
            feature_array[pos_inf] = np.finfo(np.float64).max
            feature_array[neg_inf] = -np.finfo(np.float64).max

        return feature_array
        
    def predict_flow(self, flow: Flow) -> Dict[str, Any]:
        """
        Predict attack type from flow
        
        Args:
            flow: Flow object
        
        Returns:
            Prediction dictionary with attack_type, confidence, severity
        """
        if not self.model_loader.is_loaded:
            raise ValueError("Model not loaded")
        
        # Extract features
        features = self.feature_extractor.extract_features(flow)
        
        # Validate and convert to fixed order array
        feature_array = self._validate_features(features)
        feature_array = feature_array.reshape(1, -1)
        
        # Make prediction
        try:
            predicted_class = self.model_loader.predict(feature_array)[0]
            probabilities = self.model_loader.predict_proba(feature_array)[0]
            
            # Get class name
            class_names = self.model_loader.get_class_names()
            if predicted_class < len(class_names):
                attack_type = class_names[predicted_class]
            else:
                attack_type = "Unknown"
            
            # Get confidence
            confidence = float(max(probabilities))
            
            # Determine severity based on confidence
            severity = self._determine_severity(confidence, attack_type)
            
            self.total_predictions += 1
            if attack_type != "Normal":
                self.attack_predictions += 1
            
            result = {
                'attack_type': attack_type,
                'confidence': confidence,
                'severity': severity,
                'all_probabilities': {
                    class_names[i]: float(prob)
                    for i, prob in enumerate(probabilities)
                },
                'features': features,
                'timestamp': datetime.utcnow().isoformat(),
                'model_name': self.model_loader.model_type,
                'model_version': '1.0'
            }
            
            logger.debug(f"Prediction: {attack_type} (confidence: {confidence:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            raise
    
    def predict_batch(self, flows: list) -> list:
        """
        Predict attacks from multiple flows
        
        Args:
            flows: List of Flow objects
        
        Returns:
            List of prediction dictionaries
        """
        if not self.model_loader.is_loaded:
            raise ValueError("Model not loaded")
        
        # Extract features for all flows
        features_list = self.feature_extractor.extract_features_batch(flows)
        
        # Validate and convert to fixed order array
        feature_array = np.array([self._validate_features(f) for f in features_list])
        
        # Make predictions
        try:
            predicted_classes = self.model_loader.predict(feature_array)
            probabilities = self.model_loader.predict_proba(feature_array)
            
            class_names = self.model_loader.get_class_names()
            
            results = []
            for i, (pred_class, probs) in enumerate(zip(predicted_classes, probabilities)):
                if pred_class < len(class_names):
                    attack_type = class_names[pred_class]
                else:
                    attack_type = "Unknown"
                
                confidence = float(max(probs))
                severity = self._determine_severity(confidence, attack_type)
                
                self.total_predictions += 1
                if attack_type != "Normal":
                    self.attack_predictions += 1
                
                results.append({
                    'attack_type': attack_type,
                    'confidence': confidence,
                    'severity': severity,
                    'all_probabilities': {
                        class_names[j]: float(prob)
                        for j, prob in enumerate(probs)
                    },
                    'features': features_list[i],
                    'timestamp': datetime.utcnow().isoformat(),
                    'model_name': self.model_loader.model_type,
                    'model_version': '1.0'
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Batch prediction error: {e}")
            raise
    
    def _determine_severity(self, confidence: float, attack_type: str) -> str:
        """
        Determine severity based on confidence and attack type
        
        Args:
            confidence: Prediction confidence
            attack_type: Predicted attack type
        
        Returns:
            Severity level (critical, high, medium, low)
        """
        if attack_type == "Normal":
            return "low"
        
        if confidence >= 0.9:
            return "critical"
        elif confidence >= 0.8:
            return "high"
        elif confidence >= self.confidence_threshold:
            return "medium"
        else:
            return "low"
    
    def is_attack(self, prediction: Dict[str, Any]) -> bool:
        """
        Check if prediction indicates an attack
        
        Args:
            prediction: Prediction dictionary
        
        Returns:
            True if attack, False otherwise
        """
        return (
            prediction['attack_type'] != "Normal" and
            prediction['confidence'] >= self.confidence_threshold
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get predictor statistics"""
        attack_rate = (
            self.attack_predictions / self.total_predictions
            if self.total_predictions > 0 else 0
        )
        
        return {
            'total_predictions': self.total_predictions,
            'attack_predictions': self.attack_predictions,
            'attack_rate': attack_rate,
            'confidence_threshold': self.confidence_threshold,
            'model_loaded': self.model_loader.is_loaded
        }
    
    def set_confidence_threshold(self, threshold: float):
        """
        Set confidence threshold
        
        Args:
            threshold: New threshold value (0.0 - 1.0)
        """
        if 0.0 <= threshold <= 1.0:
            self.confidence_threshold = threshold
            logger.info(f"Confidence threshold set to {threshold}")
        else:
            raise ValueError("Threshold must be between 0.0 and 1.0")


# Singleton instance
_predictor_instance: Optional[Predictor] = None


def get_predictor(
    model_loader: Optional[ModelLoader] = None,
    feature_extractor: Optional[FeatureExtractor] = None,
    confidence_threshold: float = 0.75
) -> Predictor:
    """
    Get or create predictor instance
    
    Args:
        model_loader: Model loader instance
        feature_extractor: Feature extractor instance
        confidence_threshold: Confidence threshold
    
    Returns:
        Predictor instance
    """
    global _predictor_instance
    
    if _predictor_instance is None:
        _predictor_instance = Predictor(
            model_loader=model_loader,
            feature_extractor=feature_extractor,
            confidence_threshold=confidence_threshold
        )
    
    return _predictor_instance
