"""
Database Repository
Repository layer for database operations
"""

import logging
from typing import Optional, List, Dict, Any
import bcrypt
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from backend.database.models import (
    TrafficFlow, FlowFeature, AttackAlert, AttackHistory,
    Model, Whitelist, User, Blacklist, GeoBlockRule, SecurityReport, Server, ServerMetricHistory,
    AuditLog, BlockHistory, GeoAllowRule, GeoWatchRule, SystemSetting,
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
                start_time=datetime.fromisoformat(flow_data.get('start_time', datetime.now(timezone.utc).isoformat())),
                last_seen=datetime.fromisoformat(flow_data.get('last_seen', datetime.now(timezone.utc).isoformat())),
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
            
            flow.last_seen = datetime.now(timezone.utc)
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
                timestamp=datetime.fromisoformat(alert_data.get('timestamp', datetime.now(timezone.utc).isoformat()))
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
                alert.resolved_at = datetime.now(timezone.utc)
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
                history.last_seen = datetime.now(timezone.utc)
                
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
                    first_seen=datetime.now(timezone.utc),
                    last_seen=datetime.now(timezone.utc),
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


class BlacklistRepository:
    """Repository for blacklist operations"""

    @staticmethod
    def create(db: Session, ip_address: str, reason: str = None,
               country_code: str = None, auto_blocked: bool = False,
               expires_at: datetime = None) -> Blacklist:
        try:
            entry = Blacklist(
                ip_address=ip_address, reason=reason,
                country_code=country_code, auto_blocked=auto_blocked,
                expires_at=expires_at,
            )
            db.add(entry)
            db.commit()
            db.refresh(entry)
            return entry
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating blacklist entry: {e}")
            raise

    @staticmethod
    def get_by_ip(db: Session, ip_address: str) -> Optional[Blacklist]:
        return db.query(Blacklist).filter(Blacklist.ip_address == ip_address).first()

    @staticmethod
    def get_all_active(db: Session) -> List[Blacklist]:
        return db.query(Blacklist).filter(
            Blacklist.is_active == True,
            or_(Blacklist.expires_at == None, Blacklist.expires_at > datetime.now(timezone.utc))
        ).all()

    @staticmethod
    def get_expired(db: Session) -> List[Blacklist]:
        """Lấy danh sách các IP đã hết hạn chặn nhưng vẫn đang ở trạng thái active."""
        return db.query(Blacklist).filter(
            Blacklist.is_active == True,
            Blacklist.expires_at <= datetime.now(timezone.utc)
        ).all()

    @staticmethod
    def batch_deactivate(db: Session, ip_addresses: List[str]) -> int:
        """Cập nhật trạng thái không hoạt động cho danh sách IP trong một transaction."""
        if not ip_addresses:
            return 0
        updated = db.query(Blacklist).filter(
            Blacklist.ip_address.in_(ip_addresses)
        ).update({"is_active": False}, synchronize_session=False)
        db.commit()
        return updated

    @staticmethod
    def deactivate(db: Session, ip_address: str) -> bool:
        entry = BlacklistRepository.get_by_ip(db, ip_address)
        if not entry:
            return False
        entry.is_active = False
        db.commit()
        return True


class GeoBlockRepository:
    """Repository for geo-block rules"""

    @staticmethod
    def add_rule(db: Session, country_code: str, country_name: str = None) -> GeoBlockRule:
        try:
            rule = GeoBlockRule(country_code=country_code.upper(), country_name=country_name)
            db.add(rule)
            db.commit()
            db.refresh(rule)
            return rule
        except Exception as e:
            db.rollback()
            raise

    @staticmethod
    def get_active_codes(db: Session) -> List[str]:
        rows = db.query(GeoBlockRule.country_code).filter(GeoBlockRule.is_active == True).all()
        return [r[0] for r in rows]

    @staticmethod
    def remove_rule(db: Session, country_code: str) -> bool:
        rule = db.query(GeoBlockRule).filter(
            GeoBlockRule.country_code == country_code.upper()
        ).first()
        if not rule:
            return False
        db.delete(rule)
        db.commit()
        return True

    @staticmethod
    def get_all(db: Session) -> List[GeoBlockRule]:
        return db.query(GeoBlockRule).order_by(GeoBlockRule.country_code).all()


class SecurityReportRepository:
    """Repository for security reports"""

    @staticmethod
    def create(db: Session, report_data: Dict[str, Any]) -> SecurityReport:
        try:
            report = SecurityReport(**report_data)
            db.add(report)
            db.commit()
            db.refresh(report)
            return report
        except Exception as e:
            db.rollback()
            raise

    @staticmethod
    def get_latest(db: Session, limit: int = 10) -> List[SecurityReport]:
        return db.query(SecurityReport).order_by(
            SecurityReport.created_at.desc()
        ).limit(limit).all()
    
    @staticmethod
    def get_by_report_id(db: Session, report_id: str) -> Optional[SecurityReport]:
        return db.query(SecurityReport).filter(SecurityReport.report_id == report_id).first()


# --- Server Management ---



class ServerRepository:
    """Repository cho các thao tác quản lý máy chủ."""

    @staticmethod
    def create_server(db: Session, name: str, ip_address: str, os: Optional[str] = None,
                      description: Optional[str] = None) -> Server:
        """Tạo một máy chủ mới."""
        try:
            server = Server(name=name, ip_address=ip_address, os=os, description=description)
            db.add(server)
            db.commit()
            db.refresh(server)
            logger.info(f"Created server: {name} ({ip_address})")
            return server
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating server {name}: {e}")
            raise

    @staticmethod
    def get_server_by_id(db: Session, server_id: int) -> Optional[Server]:
        """Lấy thông tin máy chủ theo ID."""
        return db.query(Server).filter(Server.id == server_id).first()

    @staticmethod
    def get_server_by_ip(db: Session, ip_address: str) -> Optional[Server]:
        """Lấy thông tin máy chủ theo địa chỉ IP."""
        return db.query(Server).filter(Server.ip_address == ip_address).first()

    @staticmethod
    def get_all_servers(db: Session) -> List[Server]:
        """Lấy tất cả các máy chủ."""
        return db.query(Server).order_by(Server.name).all()

    @staticmethod
    def update_server_status(db: Session, server_id: int, new_status: str) -> Optional[Server]:
        """Cập nhật trạng thái của một máy chủ."""
        server = ServerRepository.get_server_by_id(db, server_id)
        if not server:
            return None
        if server.status != new_status: # Chỉ cập nhật nếu trạng thái thay đổi
            server.status = new_status
            db.commit()
            db.refresh(server)
            logger.info(f"Updated server {server.name} ({server.ip_address}) status to: {new_status}")
        return server

    @staticmethod
    def update_server(db: Session, server_id: int, name: Optional[str] = None,
                      ip_address: Optional[str] = None, os: Optional[str] = None,
                      description: Optional[str] = None, status: Optional[str] = None,
                      cpu_usage: Optional[float] = None, ram_usage: Optional[float] = None,
                      disk_usage: Optional[float] = None, firewall_status: Optional[str] = None) -> Optional[Server]:
        """Cập nhật thông tin máy chủ."""
        try:
            server = ServerRepository.get_server_by_id(db, server_id)
            if not server:
                return None
            
            update_data = {k: v for k, v in locals().items() if v is not None and k not in ['db', 'server_id', 'self']}
            for key, value in update_data.items():
                setattr(server, key, value)
            server.last_seen = datetime.now(timezone.utc) # Cập nhật last_seen khi có bất kỳ update nào
            db.commit()
            db.refresh(server)
            logger.info(f"Updated server: {server.name} ({server.ip_address})")
            return server
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating server {server_id}: {e}")
            raise

    @staticmethod
    def delete_server(db: Session, server_id: int) -> bool:
        """Xóa một máy chủ."""
        try:
            server = ServerRepository.get_server_by_id(db, server_id)
            if not server:
                return False
            db.delete(server)
            db.commit()
            logger.info(f"Deleted server: {server.name} ({server.ip_address})")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting server {server_id}: {e}")
            raise


class ServerMetricHistoryRepository:
    """Repository cho lịch sử các chỉ số của máy chủ."""

    @staticmethod
    def create_history_entry(db: Session, server_id: int, cpu_usage: float, ram_usage: float,
                             disk_usage: float, status: str, firewall_status: Optional[str] = None) -> ServerMetricHistory:
        """Tạo một bản ghi lịch sử chỉ số mới."""
        try:
            entry = ServerMetricHistory(
                server_id=server_id,
                cpu_usage=cpu_usage,
                ram_usage=ram_usage,
                disk_usage=disk_usage,
                status=status,
                firewall_status=firewall_status
            )
            db.add(entry)
            db.commit()
            db.refresh(entry)
            return entry
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating server metric history for server {server_id}: {e}")
            raise

    @staticmethod
    def get_history_for_server(db: Session, server_id: int, limit: int = 100) -> List[ServerMetricHistory]:
        """Lấy lịch sử chỉ số của một máy chủ."""
        return db.query(ServerMetricHistory).filter(
            ServerMetricHistory.server_id == server_id
        ).order_by(ServerMetricHistory.timestamp.desc()).limit(limit).all()


class SettingRepository:
    """Repository quản lý cấu hình hệ thống"""
    
    @staticmethod
    def get_value(db: Session, key: str, default: Any = None) -> Any:
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        return setting.value if setting else default

    @staticmethod
    def update_value(db: Session, key: str, value: Any) -> SystemSetting:
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if setting:
            setting.value = value
        else:
            setting = SystemSetting(key=key, value=value)
            db.add(setting)
        db.commit()
        db.refresh(setting)
        return setting

class UserRepository:
    """Repository quản lý người dùng và xác thực"""

    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[User]:
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_all(db: Session) -> List[User]:
        return db.query(User).all()

    @staticmethod
    def create(db: Session, user_data: Dict[str, Any]) -> User:
        pwd = user_data['password'].encode('utf-8')[:72]
        user = User(
            username=user_data['username'],
            email=user_data.get('email', f"{user_data['username']}@zsentinel.local"),
            password_hash=bcrypt.hashpw(pwd, bcrypt.gensalt()).decode('utf-8'),
            role=user_data.get('role', 'operator')
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def update_password(db: Session, user_id: int, new_password: str):
        import bcrypt
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            pwd = new_password.encode('utf-8')[:72]
            user.password_hash = bcrypt.hashpw(pwd, bcrypt.gensalt()).decode('utf-8')
            db.commit()
            return True
        return False

    @staticmethod
    def update_role(db: Session, user_id: int, new_role: str):
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.role = new_role
            db.commit()
            return True
        return False

    @staticmethod
    def reset_password(db: Session, user_id: int, new_password_hash: str):
        """Đặt lại mật khẩu cho người dùng bằng password hash mới."""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.password_hash = new_password_hash
            db.commit()
            db.refresh(user)
            return True
        return False

    @staticmethod
    def delete(db: Session, user_id: int):
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            db.delete(user)
            db.commit()
            return True
        return False


class AuditLogRepository:
    @staticmethod
    def record(
        db: Session,
        username: str,
        action: str,
        *,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        client_ip: Optional[str] = None,
    ) -> AuditLog:
        entry = AuditLog(
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            client_ip=client_ip,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def list_entries(
        db: Session,
        limit: int = 100,
        skip: int = 0,
        action: Optional[str] = None,
        username: Optional[str] = None,
    ) -> List[AuditLog]:
        q = db.query(AuditLog)
        if action:
            q = q.filter(AuditLog.action == action)
        if username:
            q = q.filter(AuditLog.username == username)
        return q.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()


class BlockHistoryRepository:
    @staticmethod
    def record(
        db: Session,
        ip_address: str,
        action: str,
        reason: Optional[str] = None,
        duration_hours: Optional[int] = None,
        performed_by: Optional[str] = None,
        auto_blocked: bool = False,
    ) -> BlockHistory:
        entry = BlockHistory(
            ip_address=ip_address,
            action=action,
            reason=reason,
            duration_hours=duration_hours,
            performed_by=performed_by,
            auto_blocked=auto_blocked,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def list_entries(
        db: Session,
        limit: int = 100,
        ip_address: Optional[str] = None,
    ) -> List[BlockHistory]:
        q = db.query(BlockHistory)
        if ip_address:
            q = q.filter(BlockHistory.ip_address == ip_address)
        return q.order_by(BlockHistory.created_at.desc()).limit(limit).all()


class _GeoPolicyRepoBase:
    model = None

    @classmethod
    def add_rule(cls, db: Session, country_code: str, country_name: str = None):
        code = country_code.upper()
        rule = cls.model(country_code=code, country_name=country_name)
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return rule

    @classmethod
    def get_active_codes(cls, db: Session) -> List[str]:
        rows = db.query(cls.model.country_code).filter(cls.model.is_active == True).all()
        return [r[0] for r in rows]

    @classmethod
    def get_all(cls, db: Session):
        return db.query(cls.model).order_by(cls.model.country_code).all()

    @classmethod
    def remove_rule(cls, db: Session, country_code: str) -> bool:
        rule = db.query(cls.model).filter(cls.model.country_code == country_code.upper()).first()
        if not rule:
            return False
        db.delete(rule)
        db.commit()
        return True


class GeoAllowRepository(_GeoPolicyRepoBase):
    model = GeoAllowRule


class GeoWatchRepository(_GeoPolicyRepoBase):
    model = GeoWatchRule
