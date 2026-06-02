"""
Alert Manager
Enhanced alert generation with severity scoring, cooldown, and correlation
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

from sqlalchemy.orm import Session

from backend.database.connection import SessionLocal
from backend.database.repository import (
    AttackAlertRepository,
    AttackHistoryRepository,
    TrafficFlowRepository,
    FlowFeatureRepository
)
from backend.notifications.email import email_service
from backend.cache.redis_cache import get_cache

logger = logging.getLogger(__name__)


class AlertManager:
    """Manage alert generation with cooldown and correlation"""
    
    def __init__(
        self,
        confidence_threshold: float = 0.75,
        alert_cooldown: int = 30,
        correlation_window: int = 60,
        enable_db_save: bool = True,
        enable_websocket: bool = True,
        enable_email: bool = True
    ):
        """
        Initialize alert manager
        
        Args:
            confidence_threshold: Minimum confidence for alert generation
            alert_cooldown: Cooldown period for same attacker IP (seconds)
            correlation_window: Window for correlation analysis (seconds)
            enable_db_save: Enable saving alerts to database
            enable_websocket: Enable WebSocket broadcast
            enable_email: Enable email alert dispatch (still gated by
                          ENABLE_EMAIL_ALERTS env var and severity/confidence)
        """
        self.confidence_threshold = confidence_threshold
        self.alert_cooldown = alert_cooldown
        self.correlation_window = correlation_window
        self.enable_db_save = enable_db_save
        self.enable_websocket = enable_websocket
        self.enable_email = enable_email
        
        # Alert history for cooldown
        self.alert_history: Dict[str, datetime] = {}
        
        # Attack correlation tracking
        self.attack_patterns: Dict[str, List[Dict]] = defaultdict(list)
        
        # Whitelist
        self.whitelist: set = set()
        
        # Statistics
        self.total_alerts = 0
        self.alerts_by_type: Dict[str, int] = defaultdict(int)
        self.alerts_by_severity: Dict[str, int] = defaultdict(int)
        
        # Thread-safe broadcast bridge (set at app startup; never call async WS from sniffer thread)
        self.broadcast_bridge = None
    
    def generate_alert(
        self,
        prediction: Dict,
        flow_info: Dict,
        flow_id: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Generate alert from prediction with cooldown and correlation
        
        Args:
            prediction: Prediction dictionary from predictor
            flow_info: Flow information
            flow_id: Database flow ID for linking
        
        Returns:
            Alert dictionary or None if suppressed
        """
        attack_type = prediction.get('attack_type', 'Normal')
        confidence = prediction.get('confidence', 0.0)
        severity = prediction.get('severity', 'low')
        
        # Skip normal traffic
        if attack_type == 'Normal':
            return None
        
        # Check confidence threshold
        if confidence < self.confidence_threshold:
            logger.debug(f"Confidence below threshold: {confidence:.2f} < {self.confidence_threshold}")
            return None
        
        # Extract source IP
        src_ip = flow_info.get('src_ip')
        if not src_ip:
            logger.warning("Flow missing source IP")
            return None
        
        # Check whitelist
        if self._is_whitelisted(src_ip):
            logger.debug(f"IP whitelisted: {src_ip}")
            return None
        
        # Check cooldown
        if self._is_in_cooldown(src_ip):
            logger.debug(f"IP in cooldown: {src_ip}")
            return None
        
        # Apply correlation logic
        adjusted_severity = self._apply_correlation(src_ip, attack_type, severity)
        
        # Generate alert
        alert = {
            'alert_id': str(uuid.uuid4()),
            'src_ip': src_ip,
            'dst_ip': flow_info.get('dst_ip'),
            'src_port': flow_info.get('src_port'),
            'dst_port': flow_info.get('dst_port'),
            'protocol': flow_info.get('protocol'),
            'attack_type': attack_type,
            'confidence': confidence,
            'severity': adjusted_severity,
            'original_severity': severity,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'active',
            'flow_key': flow_info.get('flow_key'),
            'features': prediction.get('features', {}),
            'correlated': adjusted_severity != severity,
            'all_probabilities': prediction.get('all_probabilities', {}),
            'model_name': prediction.get('model_name'),
            'model_version': prediction.get('model_version', '1.0')
        }
        
        # Update tracking
        self._update_alert_history(src_ip)
        self._update_attack_patterns(src_ip, attack_type, alert)
        self._update_statistics(attack_type, adjusted_severity)
        
        self.total_alerts += 1
        logger.info(f"Alert generated: {attack_type} from {src_ip} (severity: {adjusted_severity})")
        
        # Save to database
        if self.enable_db_save:
            self._save_alert_to_db(alert, flow_id)
        
        # Update attack history
        if self.enable_db_save:
            self._update_attack_history_db(src_ip, attack_type, adjusted_severity)
        
        # Enqueue for async WebSocket broadcast (non-blocking, thread-safe)
        if self.enable_websocket and self.broadcast_bridge is not None:
            self.broadcast_bridge.enqueue_alert(alert)

        # Dispatch email notification (non-blocking asyncio task; gated by
        # ENABLE_EMAIL_ALERTS, severity, confidence, and per-IP cooldown)
        if self.enable_email:
            email_service.dispatch_alert_email(alert)

        return alert
    
    def _is_whitelisted(self, ip_address: str) -> bool:
        """Check if IP is whitelisted"""
        return ip_address in self.whitelist
    
    def _is_in_cooldown(self, ip_address: str) -> bool:
        """Check cooldown via Redis (falls back to in-memory if Redis unavailable)."""
        cache = get_cache()
        if cache.is_connected():
            return cache.is_alert_in_cooldown(ip_address)
        # in-memory fallback
        if ip_address not in self.alert_history:
            return False
        return datetime.utcnow() < self.alert_history[ip_address] + timedelta(seconds=self.alert_cooldown)

    def _update_alert_history(self, ip_address: str):
        """Record cooldown in Redis (and in-memory as fallback)."""
        cache = get_cache()
        if cache.is_connected():
            cache.set_alert_cooldown(ip_address, self.alert_cooldown)
        self.alert_history[ip_address] = datetime.utcnow()
    
    def _apply_correlation(
        self,
        src_ip: str,
        attack_type: str,
        current_severity: str
    ) -> str:
        """
        Apply correlation logic to adjust severity
        
        Args:
            src_ip: Source IP address
            attack_type: Attack type
            current_severity: Current severity level
        
        Returns:
            Adjusted severity level
        """
        # Get recent attacks from this IP
        current_time = datetime.utcnow()
        window_start = current_time - timedelta(seconds=self.correlation_window)
        
        recent_attacks = [
            alert for alert in self.attack_patterns[src_ip]
            if datetime.fromisoformat(alert['timestamp']) >= window_start
        ]
        
        # Count attacks by type
        attack_counts = defaultdict(int)
        for alert in recent_attacks:
            attack_counts[alert['attack_type']] += 1
        
        # Correlation logic
        total_recent = len(recent_attacks)
        
        # Repeated scan attempts => higher severity
        if total_recent >= 5:
            if current_severity in ['low', 'medium']:
                return 'high'
            elif current_severity == 'high':
                return 'critical'
        
        # Port scanning pattern
        if attack_type in ['PortScan', 'Port Sweep']:
            if total_recent >= 3:
                return 'critical'
        
        # DDoS pattern
        if attack_type == 'DDoS':
            if total_recent >= 2:
                return 'critical'
        
        return current_severity
    
    def _update_attack_patterns(
        self,
        src_ip: str,
        attack_type: str,
        alert: Dict
    ):
        """Update attack patterns for correlation"""
        self.attack_patterns[src_ip].append(alert)
        
        # Clean old patterns outside correlation window
        current_time = datetime.utcnow()
        window_start = current_time - timedelta(seconds=self.correlation_window)
        
        self.attack_patterns[src_ip] = [
            alert for alert in self.attack_patterns[src_ip]
            if datetime.fromisoformat(alert['timestamp']) >= window_start
        ]
    
    def _update_statistics(self, attack_type: str, severity: str):
        """Update alert statistics"""
        self.alerts_by_type[attack_type] += 1
        self.alerts_by_severity[severity] += 1
    
    def _save_alert_to_db(self, alert: Dict, flow_id: Optional[int] = None):
        """Save alert to database"""
        try:
            db = SessionLocal()
            try:
                AttackAlertRepository.create_alert(db, alert, flow_id)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error saving alert to database: {e}")
    
    def _update_attack_history_db(self, src_ip: str, attack_type: str, severity: str):
        """Update attack history in database"""
        try:
            db = SessionLocal()
            try:
                AttackHistoryRepository.update_or_create_history(db, src_ip, attack_type, severity)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error updating attack history: {e}")
    
    def set_broadcast_bridge(self, bridge) -> None:
        """Attach thread-safe alert broadcast bridge (FastAPI lifespan)."""
        self.broadcast_bridge = bridge
        logger.info("Alert broadcast bridge attached to AlertManager")

    def set_websocket_manager(self, manager) -> None:
        """Deprecated: use set_broadcast_bridge(). Kept for backward compatibility."""
        logger.warning(
            "set_websocket_manager() is deprecated; alerts use AlertBroadcastBridge"
        )
    
    def add_to_whitelist(self, ip_address: str):
        """Add IP to whitelist"""
        self.whitelist.add(ip_address)
        logger.info(f"Added {ip_address} to whitelist")
    
    def remove_from_whitelist(self, ip_address: str):
        """Remove IP from whitelist"""
        if ip_address in self.whitelist:
            self.whitelist.remove(ip_address)
            logger.info(f"Removed {ip_address} from whitelist")
    
    def get_whitelist(self) -> List[str]:
        """Get whitelist"""
        return list(self.whitelist)
    
    def get_alert_history(self, ip_address: str) -> List[Dict]:
        """Get alert history for an IP"""
        if ip_address not in self.attack_patterns:
            return []
        
        return self.attack_patterns[ip_address]
    
    def get_stats(self) -> Dict:
        """Get alert manager statistics"""
        return {
            'total_alerts': self.total_alerts,
            'alerts_by_type': dict(self.alerts_by_type),
            'alerts_by_severity': dict(self.alerts_by_severity),
            'whitelist_count': len(self.whitelist),
            'active_attackers': len(self.attack_patterns),
            'confidence_threshold': self.confidence_threshold,
            'alert_cooldown': self.alert_cooldown,
            'correlation_window': self.correlation_window
        }
    
    def clear_history(self, ip_address: Optional[str] = None):
        """
        Clear alert history
        
        Args:
            ip_address: Specific IP to clear, or None to clear all
        """
        if ip_address:
            if ip_address in self.alert_history:
                del self.alert_history[ip_address]
            if ip_address in self.attack_patterns:
                del self.attack_patterns[ip_address]
            logger.info(f"Cleared history for {ip_address}")
        else:
            self.alert_history.clear()
            self.attack_patterns.clear()
            logger.info("Cleared all alert history")


# Singleton instance
_alert_manager_instance: Optional[AlertManager] = None


def get_alert_manager(
    confidence_threshold: float = 0.75,
    alert_cooldown: int = 30,
    correlation_window: int = 60
) -> AlertManager:
    """
    Get or create alert manager instance
    
    Args:
        confidence_threshold: Confidence threshold
        alert_cooldown: Alert cooldown period
        correlation_window: Correlation window
    
    Returns:
        AlertManager instance
    """
    global _alert_manager_instance
    
    if _alert_manager_instance is None:
        _alert_manager_instance = AlertManager(
            confidence_threshold=confidence_threshold,
            alert_cooldown=alert_cooldown,
            correlation_window=correlation_window
        )
    
    return _alert_manager_instance
