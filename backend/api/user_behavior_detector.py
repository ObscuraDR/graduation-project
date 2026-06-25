import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from backend.database.models import AuditLog
from backend.alert_engine.alert_manager import get_alert_manager

logger = logging.getLogger(__name__)

class UserBehaviorDetector:
    """
    Phân tích Audit Logs để phát hiện hành vi người dùng đáng ngờ (UEBA).
    """
    def __init__(self, db: Session):
        self.db = db
        self.alert_manager = get_alert_manager()

    def check_velocity_attack(self, username: str, window_minutes: int = 5):
        """
        Phát hiện nếu một user thực hiện quá nhiều hành động nhạy cảm trong thời gian ngắn.
        """
        time_threshold = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        
        # Danh sách các hành động nhạy cảm
        critical_actions = ["update_user_role", "delete_user", "reset_password", "block_ip"]
        
        count = self.db.query(AuditLog).filter(
            AuditLog.username == username,
            AuditLog.action.in_(critical_actions),
            AuditLog.created_at >= time_threshold
        ).count()

        if count >= 3:  # Ngưỡng: 3 hành động nhạy cảm trong 5 phút
            self._generate_behavioral_alert(username, f"Phát hiện thao tác nhạy cảm liên tục ({count} lần)")

    def _generate_behavioral_alert(self, username: str, description: str):
        prediction = {
            'attack_type': 'Suspicious User Behavior',
            'confidence': 0.85,
            'severity': 'high',
            'description': description
        }
        # Giả lập flow info cho hệ thống alert hiện tại
        flow_info = {'src_ip': '127.0.0.1', 'dst_ip': 'system', 'user': username}
        
        logger.warning("UEBA ALERT: User %s - %s", username, description)
        self.alert_manager.generate_alert(prediction, flow_info)