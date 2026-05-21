"""
Database Repository
Repository layer for database operations
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from backend.database.models import (
    TrafficFlow, FlowFeature, AttackAlert, AttackHistory,
    Model, Whitelist, User
)

logger = logging.getLogger(__name__)


class TrafficFlowRepository:
    """Repository for traffic flow operations"""
    
    @staticmethod
    def create_flow(db: Session, flow_data: Dict[str, Any]) -> TrafficFlow:
        """Create a new traffic flow"""
        try:
            flow = TrafficFlow(
                flow_key=flow_data.get('flow_key'),
                src_ip=flow_data.get('src_ip'),
                dst_ip=flow_data.get('dst_ip'),
                src_port=flow_data.get('src_port'),
                dst_port=flow_data.get('dst_port'),
                protocol=flow_data.get('protocol'),
                packet_count=flow_data.get('packet_count', 0),
                byte_count=flow_data.get('byte_count', 0),
                forward_packets=flow_data.get('forward_packets', 0),
                backward_packets=flow_data.get('backward_packets', 0),
                forward_bytes=flow_data.get('forward_bytes', 0),
                backward_bytes=flow_data.get('backward_bytes', 0),
                syn_count=flow_data.get('syn_count', 0),
                fin_count=flow_data.get('fin_count', 0),
                rst_count=flow_data.get('rst_count', 0),
                psh_count=flow_data.get('psh_count', 0),
                ack_count=flow_data.get('ack_count', 0),
                flow_duration=flow_data.get('flow_duration', 0.0),
                start_time=datetime.fromisoformat(flow_data.get('start_time', datetime.utcnow().isoformat())),
                last_seen=datetime.fromisoformat(flow_data.get('last_seen', datetime.utcnow().isoformat())),
                inter_arrival_time_mean=flow_data.get('inter_arrival_time_mean', 0.0),
                unique_dst_ports=flow_data.get('unique_dst_ports', 0)
            )
            db.add(flow)
            db.commit()
            db.refresh(flow)
            logger.debug(f"Created traffic flow: {flow.flow_key}")
            return flow
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating traffic flow: {e}")
            raise
    
    @staticmethod
    def get_flow_by_key(db: Session, flow_key: str) -> Optional[TrafficFlow]:
        """Get flow by flow_key"""
        return db.query(TrafficFlow).filter(TrafficFlow.flow_key == flow_key).first()
    
    @staticmethod
    def get_flows_by_source_ip(db: Session, src_ip: str, limit: int = 100) -> List[TrafficFlow]:
        """Get flows by source IP"""
        return db.query(TrafficFlow).filter(
            TrafficFlow.src_ip == src_ip
        ).order_by(TrafficFlow.last_seen.desc()).limit(limit).all()
    
    @staticmethod
    def update_flow(db: Session, flow_key: str, flow_data: Dict[str, Any]) -> Optional[TrafficFlow]:
        """Update existing flow"""
        try:
            flow = TrafficFlowRepository.get_flow_by_key(db, flow_key)
            if not flow:
                return None
            
            for key, value in flow_data.items():
                if hasattr(flow, key) and key != 'flow_key':
                    setattr(flow, key, value)
            
            flow.last_seen = datetime.utcnow()
            db.commit()
            db.refresh(flow)
            return flow
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating flow: {e}")
            raise


class FlowFeatureRepository:
    """Repository for flow feature operations"""
    
    @staticmethod
    def create_feature(db: Session, feature_data: Dict[str, Any], flow_id: Optional[int] = None) -> FlowFeature:
        """Create a new flow feature record"""
        try:
            feature = FlowFeature(
                flow_id=flow_id,
                flow_duration=feature_data.get('flow_duration', 0.0),
                total_fwd_packets=feature_data.get('total_fwd_packets', 0),
                total_bwd_packets=feature_data.get('total_bwd_packets', 0),
                total_fwd_bytes=feature_data.get('total_fwd_bytes', 0),
                total_bwd_bytes=feature_data.get('total_bwd_bytes', 0),
                avg_packet_size=feature_data.get('avg_packet_size', 0.0),
                packet_rate=feature_data.get('packet_rate', 0.0),
                byte_rate=feature_data.get('byte_rate', 0.0),
                syn_count=feature_data.get('syn_count', 0),
                fin_count=feature_data.get('fin_count', 0),
                rst_count=feature_data.get('rst_count', 0),
                psh_count=feature_data.get('psh_count', 0),
                ack_count=feature_data.get('ack_count', 0),
                unique_dst_ports=feature_data.get('unique_dst_ports', 0),
                inter_arrival_time_mean=feature_data.get('inter_arrival_time_mean', 0.0),
                fwd_packet_rate=feature_data.get('fwd_packet_rate', 0.0),
                bwd_packet_rate=feature_data.get('bwd_packet_rate', 0.0),
                fwd_byte_rate=feature_data.get('fwd_byte_rate', 0.0),
                bwd_byte_rate=feature_data.get('bwd_byte_rate', 0.0),
                packet_length_mean=feature_data.get('packet_length_mean', 0.0),
                feature_vector=feature_data
            )
            db.add(feature)
            db.commit()
            db.refresh(feature)
            logger.debug(f"Created flow feature for flow_id: {flow_id}")
            return feature
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating flow feature: {e}")
            raise


class AttackAlertRepository:
    """Repository for attack alert operations"""
    
    @staticmethod
    def create_alert(db: Session, alert_data: Dict[str, Any], flow_id: Optional[int] = None) -> AttackAlert:
        """Create a new attack alert"""
        try:
            alert = AttackAlert(
                alert_id=alert_data.get('alert_id'),
                flow_id=flow_id,
                source_ip=alert_data.get('src_ip'),
                dest_ip=alert_data.get('dst_ip'),
                source_port=alert_data.get('src_port'),
                dest_port=alert_data.get('dst_port'),
                protocol=alert_data.get('protocol'),
                attack_type=alert_data.get('attack_type'),
                severity=alert_data.get('severity'),
                confidence=alert_data.get('confidence'),
                correlated=alert_data.get('correlated', False),
                original_severity=alert_data.get('original_severity'),
                status=alert_data.get('status', 'active'),
                model_name=alert_data.get('model_name'),
                model_version=alert_data.get('model_version'),
                all_probabilities=alert_data.get('all_probabilities'),
                timestamp=datetime.fromisoformat(alert_data.get('timestamp', datetime.utcnow().isoformat()))
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            logger.info(f"Created attack alert: {alert.alert_id} - {alert.attack_type} from {alert.source_ip}")
            return alert
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating attack alert: {e}")
            raise
    
    @staticmethod
    def get_alert_by_id(db: Session, alert_id: str) -> Optional[AttackAlert]:
        """Get alert by alert_id"""
        return db.query(AttackAlert).filter(AttackAlert.alert_id == alert_id).first()
    
    @staticmethod
    def get_alerts(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        attack_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[AttackAlert]:
        """Get alerts with optional filtering"""
        query = db.query(AttackAlert)
        
        if severity:
            query = query.filter(AttackAlert.severity == severity)
        if status:
            query = query.filter(AttackAlert.status == status)
        if attack_type:
            query = query.filter(AttackAlert.attack_type == attack_type)
        if start_time:
            query = query.filter(AttackAlert.timestamp >= start_time)
        if end_time:
            query = query.filter(AttackAlert.timestamp <= end_time)
        
        return query.order_by(AttackAlert.timestamp.desc()).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_alert_status(db: Session, alert_id: str, status: str, notes: Optional[str] = None) -> Optional[AttackAlert]:
        """Update alert status"""
        try:
            alert = AttackAlertRepository.get_alert_by_id(db, alert_id)
            if not alert:
                return None
            
            alert.status = status
            alert.is_resolved = (status == "resolved")
            if status == "resolved":
                alert.resolved_at = datetime.utcnow()
            if notes:
                alert.notes = notes
            
            db.commit()
            db.refresh(alert)
            logger.info(f"Updated alert {alert_id} to status: {status}")
            return alert
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating alert status: {e}")
            raise


class AttackHistoryRepository:
    """Repository for attack history operations"""
    
    @staticmethod
    def update_or_create_history(db: Session, src_ip: str, attack_type: str, severity: str) -> AttackHistory:
        """Update or create attack history for an IP"""
        try:
            history = db.query(AttackHistory).filter(
                and_(
                    AttackHistory.source_ip == src_ip,
                    AttackHistory.attack_type == attack_type
                )
            ).first()
            
            if history:
                # Update existing history
                history.attack_count += 1
                history.last_seen = datetime.utcnow()
                
                if severity == 'critical':
                    history.critical_count += 1
                elif severity == 'high':
                    history.high_count += 1
                elif severity == 'medium':
                    history.medium_count += 1
                else:
                    history.low_count += 1
                
                db.commit()
                db.refresh(history)
                logger.debug(f"Updated attack history for {src_ip}: {attack_type}")
            else:
                # Create new history
                history = AttackHistory(
                    source_ip=src_ip,
                    attack_type=attack_type,
                    first_seen=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                    attack_count=1,
                    critical_count=1 if severity == 'critical' else 0,
                    high_count=1 if severity == 'high' else 0,
                    medium_count=1 if severity == 'medium' else 0,
                    low_count=1 if severity == 'low' else 0
                )
                db.add(history)
                db.commit()
                db.refresh(history)
                logger.debug(f"Created attack history for {src_ip}: {attack_type}")
            
            return history
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating attack history: {e}")
            raise
    
    @staticmethod
    def get_history_by_ip(db: Session, src_ip: str) -> List[AttackHistory]:
        """Get attack history for an IP"""
        return db.query(AttackHistory).filter(AttackHistory.source_ip == src_ip).all()
