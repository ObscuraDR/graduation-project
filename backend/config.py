"""
Configuration Management
Load environment variables and application settings
"""

from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import Optional, List
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
    
    # MongoDB
    mongodb_host: str = "localhost"
    mongodb_port: int = 27017
    mongodb_db: str = "ids_logs"
    mongo_uri: str = ""   # URI override; takes priority when non-empty
    mongo_db: str = "ids_logs"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: str = ""   # URI override; takes priority when non-empty
    
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
    
    # CORS
    cors_origins_str: str = ""

    @property
    def cors_origins(self) -> List[str]:
        if self.cors_origins_str:
            return [o.strip() for o in self.cors_origins_str.split(",") if o.strip()]
        if self.environment == "development":
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        return []

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        env = self.environment.lower()
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
            if not self.cors_origins_str.strip():
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
    
    # Alert Thresholds
    alert_threshold_critical: float = 0.9
    alert_threshold_high: float = 0.7
    alert_threshold_medium: float = 0.5
    
    # Model Paths
    model_dir: str = "./models"
    rf_model_path: str = "./models/random_forest.pkl"
    xgb_model_path: str = "./models/xgboost.pkl"
    lstm_model_path: str = "./models/lstm.pkl"
    ensemble_model_path: str = "./models/ensemble.pkl"
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
