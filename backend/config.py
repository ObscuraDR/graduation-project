"""
Configuration Management
Load environment variables and application settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, field_validator
from typing import Optional, List, Any, Union
from functools import lru_cache
import logging
import os


logger = logging.getLogger(__name__)

DEFAULT_SECRET_KEY = "your-secret-key-change-this-in-production"
DEFAULT_API_KEY = "changeme-set-API_KEY-in-env"


class Settings(BaseSettings):
    """Application settings"""

    # Environment
    environment: str = "development"
    
    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "ids_db"
    postgres_user: str = "ids_user"
    postgres_password: str = "ids_password"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    # API Key authentication (X-API-Key header)
    api_key: str = DEFAULT_API_KEY

    # JWT
    secret_key: str = DEFAULT_SECRET_KEY
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Auth Security (Account Lockout)
    auth_max_failed_attempts: int = 5
    auth_lockout_minutes: int = 15
    enable_account_lockout: bool = True

    # CORS
    cors_origins: Any = []

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: any) -> List[str]:
        if isinstance(v, str) and v:
            return [o.strip() for o in v.split(",") if o.strip()]
        return v or []

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        env = self.environment.lower()
        
        # Set default CORS for development if empty
        if env == "development" and not self.cors_origins:
            self.cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"]
            
        if env == "production":
            errors = []
            if self.secret_key == DEFAULT_SECRET_KEY:
                errors.append("SECRET_KEY is still the default value")
            if self.api_key == DEFAULT_API_KEY:
                errors.append("API_KEY is still the default value")
            if len(self.secret_key) < 32:
                errors.append(f"SECRET_KEY too short ({len(self.secret_key)} chars, need >= 32)")
            if len(self.api_key) < 16:
                errors.append(f"API_KEY too short ({len(self.api_key)} chars, need >= 16)")
            if not self.cors_origins:
                errors.append("CORS_ORIGINS must be set in production (no wildcard allowed)")
            if errors:
                raise RuntimeError(
                    "[PRODUCTION] Startup blocked — insecure configuration:\n  - "
                    + "\n  - ".join(errors)
                )
        elif env == "development":
            if self.secret_key == DEFAULT_SECRET_KEY:
                logger.warning("[DEV] SECRET_KEY is using the default value — change before production")
            if self.api_key == DEFAULT_API_KEY:
                logger.warning("[DEV] API_KEY is using the default value — change before production")
        return self
    
    # Request size limits
    max_request_size: int = 10 * 1024 * 1024  # 10MB

    # Live-attack replay demo (thesis defense). Disabled by default; when False
    # the /api/demo/start endpoint is refused even with a valid API key.
    enable_demo_replay: bool = True
    
    # Email alerts
    enable_email_alerts: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = "your-email@gmail.com"
    smtp_password: str = "your-app-password"
    smtp_from: str = "IDS System <noreply@ids-system.com>"
    # Comma-separated list of recipient addresses
    smtp_to: str = "soc-team@example.com"
    # Minimum seconds between emails for the same attacker IP (anti-spam)
    email_cooldown_seconds: int = 60
    
    # Log Scanner
    enable_log_scanner: bool = False
    auth_log_path: str = "/var/log/auth.log" # Or /var/log/secure for RHEL/CentOS
    ssh_brute_force_threshold: int = 5
    ssh_brute_force_window_seconds: int = 60
    ssh_brute_force_block_threshold: int = 20
    ssh_brute_force_severe_threshold: int = 100
    ssh_brute_force_block_1h_seconds: int = 3600
    ssh_brute_force_block_24h_seconds: int = 86400
    log_scan_interval_seconds: int = 5

    # Cloudflare Edge Firewall
    enable_cloudflare_firewall: bool = False
    cloudflare_api_token: str = ""
    cloudflare_zone_id: str = ""

    # Threat Intelligence
    abuseipdb_api_key: str = ""   # https://www.abuseipdb.com/account/api — free tier 1000 req/day

    # Telegram alerts
    enable_telegram_alerts: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Discord alerts
    enable_discord_alerts: bool = False
    discord_webhook_url: str = ""

    # Alert Thresholds
    alert_threshold_critical: float = 0.9
    alert_threshold_high: float = 0.7
    alert_threshold_medium: float = 0.5
    
    # Model Paths
    model_dir: str = "./backend/models"
    rf_model_path: str = "./backend/models/random_forest.pkl"
    xgb_model_path: str = "./backend/models/xgboost.pkl"

    # Server Management
    server_offline_threshold_seconds: int = 30  # Thời gian tối đa không nhận được heartbeat từ agent
    server_status_check_interval_seconds: int = 10 # Tần suất worker kiểm tra
    lstm_model_path: str = "./backend/models/lstm.pkl"
    ensemble_model_path: str = "./backend/models/ensemble.pkl"
    
    # Pipeline / flow inference
    min_packets: int = 10
    prediction_mode: str = "once"  # "once" | "window"
    prediction_interval_sec: float = 5.0
    flow_expire_sec: int = 30  # inactive flow removal
    flow_max_lifetime_sec: int = 60  # max flow age regardless of activity
    processed_flow_retention_sec: int = 45  # remove processed flows after this

    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/backend.log"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        protected_namespaces=(),  # Sửa lỗi cảnh báo model_dir
        extra="ignore"             # Cho phép bỏ qua các biến môi trường thừa
    )

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
