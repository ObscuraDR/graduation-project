"""
Feature Extractor
Extract flow-based features for ML model inference
"""

import logging
import numpy as np
from typing import Dict, List, Optional
from backend.flow_engine.flow_builder import Flow

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """Extract features from network flows for ML inference"""
    
    def __init__(self):
        self.feature_names = [
            'flow_duration',
            'total_fwd_packets',
            'total_bwd_packets',
            'total_fwd_bytes',
            'total_bwd_bytes',
            'avg_packet_size',
            'packet_rate',
            'byte_rate',
            'syn_count',
            'fin_count',
            'rst_count',
            'psh_count',
            'ack_count',
            'unique_dst_ports',
            'inter_arrival_time_mean',
            'fwd_packet_rate',
            'bwd_packet_rate',
            'fwd_byte_rate',
            'bwd_byte_rate',
            'packet_length_mean'
        ]
    
    def extract_features(self, flow: Flow) -> Dict[str, float]:
        """
        Extract features from a flow
        
        Args:
            flow: Flow object
        
        Returns:
            Dictionary of feature names and values
        """
        flow_stats = flow.get_stats()
        flow_duration = flow_stats.get('flow_duration', 0)
        
        features = {}
        
        # Basic flow features
        features['flow_duration'] = flow_duration
        features['total_fwd_packets'] = flow_stats.get('forward_packets', 0)
        features['total_bwd_packets'] = flow_stats.get('backward_packets', 0)
        features['total_fwd_bytes'] = flow_stats.get('forward_bytes', 0)
        features['total_bwd_bytes'] = flow_stats.get('backward_bytes', 0)
        
        # Packet statistics
        total_packets = flow_stats.get('packet_count', 0)
        total_bytes = flow_stats.get('byte_count', 0)
        
        features['avg_packet_size'] = total_bytes / total_packets if total_packets > 0 else 0
        features['packet_rate'] = total_packets / flow_duration if flow_duration > 0 else 0
        features['byte_rate'] = total_bytes / flow_duration if flow_duration > 0 else 0
        
        # TCP flags
        features['syn_count'] = flow_stats.get('syn_count', 0)
        features['fin_count'] = flow_stats.get('fin_count', 0)
        features['rst_count'] = flow_stats.get('rst_count', 0)
        features['psh_count'] = flow_stats.get('psh_count', 0)
        features['ack_count'] = flow_stats.get('ack_count', 0)
        
        # Unique ports
        features['unique_dst_ports'] = flow_stats.get('unique_dst_ports', 0)
        
        # Inter-arrival time
        features['inter_arrival_time_mean'] = flow_stats.get('inter_arrival_time_mean', 0)
        
        # Directional rates
        features['fwd_packet_rate'] = flow_stats.get('forward_packets', 0) / flow_duration if flow_duration > 0 else 0
        features['bwd_packet_rate'] = flow_stats.get('backward_packets', 0) / flow_duration if flow_duration > 0 else 0
        features['fwd_byte_rate'] = flow_stats.get('forward_bytes', 0) / flow_duration if flow_duration > 0 else 0
        features['bwd_byte_rate'] = flow_stats.get('backward_bytes', 0) / flow_duration if flow_duration > 0 else 0
        
        # Packet length statistics
        if total_packets > 0:
            features['packet_length_mean'] = total_bytes / total_packets
        else:
            features['packet_length_mean'] = 0
        
        # Fill missing features with 0
        for feature_name in self.feature_names:
            if feature_name not in features:
                features[feature_name] = 0.0
        
        return features
    
    def extract_features_batch(self, flows: List[Flow]) -> List[Dict[str, float]]:
        """
        Extract features from multiple flows
        
        Args:
            flows: List of Flow objects
        
        Returns:
            List of feature dictionaries
        """
        return [self.extract_features(flow) for flow in flows]
    
    def features_to_dataframe(self, features_list: List[Dict[str, float]]):
        """
        Convert feature list to pandas DataFrame
        
        Args:
            features_list: List of feature dictionaries
        
        Returns:
            pandas DataFrame
        """
        import pandas as pd
        
        df = pd.DataFrame(features_list)
        
        # Ensure all feature columns exist
        for feature_name in self.feature_names:
            if feature_name not in df.columns:
                df[feature_name] = 0.0
        
        # Reorder columns
        df = df[self.feature_names]
        
        return df
    
    def get_feature_names(self) -> List[str]:
        """Get list of feature names"""
        return self.feature_names.copy()
    
    def normalize_features(self, features: Dict[str, float], scaler=None):
        """
        Normalize features using provided scaler
        
        Args:
            features: Feature dictionary
            scaler: Fitted scaler (sklearn StandardScaler)
        
        Returns:
            Normalized feature array
        """
        import pandas as pd
        
        # Convert to DataFrame
        df = pd.DataFrame([features])
        
        # Ensure all features exist
        for feature_name in self.feature_names:
            if feature_name not in df.columns:
                df[feature_name] = 0.0
        
        # Reorder columns
        df = df[self.feature_names]
        
        # Normalize if scaler provided
        if scaler:
            return scaler.transform(df)
        
        return df.values


# Singleton instance
_feature_extractor_instance: Optional[FeatureExtractor] = None


def get_feature_extractor() -> FeatureExtractor:
    """Get or create feature extractor instance"""
    global _feature_extractor_instance
    
    if _feature_extractor_instance is None:
        _feature_extractor_instance = FeatureExtractor()
    
    return _feature_extractor_instance
