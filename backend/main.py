"""
IDS Backend - Main Application
Machine Learning-based Intrusion Detection System
"""

import sys
from pathlib import Path

# Thêm thư mục gốc của dự án vào sys.path để nhận diện package 'backend'
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import asyncio
import uuid
from pythonjsonlogger import jsonlogger

# Configure structured JSON logging
Path("logs").mkdir(exist_ok=True)

# Create JSON formatter
formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(name)s %(levelname)s %(message)s %(correlation_id)s'
)

# Setup file handler with JSON logging
file_handler = logging.FileHandler('logs/backend.log')
file_handler.setFormatter(formatter)

# Setup console handler with JSON logging
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    from backend.api.routes import sniffer as sniffer_routes
    from backend.api.websocket import get_broadcast_bridge
    from backend.alert_engine.alert_manager import get_alert_manager
    from backend.database.server_status_worker import check_server_status_task
    from backend.database.ueba_worker import ueba_detection_task
    from backend.database.firewall_worker import cleanup_expired_blacklist_task
    from backend.config import settings as app_settings

    logger.info("Starting IDS Backend...")

    # Startup: Initialize databases
    from backend.database.connection import init_db
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

    # Seed initial data (idempotent — only runs if tables are empty)
    try:
        from backend.database.init_db import seed_data
        seed_data()
        logger.info("Database seeded successfully")
    except Exception as e:
        logger.warning(f"Database seeding skipped: {e}")

    # Sync whitelist + blacklist + geo-block from DB into AlertManager
    try:
        from backend.database.connection import SessionLocal
        from backend.database.repository import BlacklistRepository, GeoBlockRepository, GeoAllowRepository, GeoWatchRepository
        from backend.database.models import Whitelist
        _db = SessionLocal()
        alert_mgr = get_alert_manager()
        try:
            for row in _db.query(Whitelist).all():
                alert_mgr.add_to_whitelist(row.ip_address)
            for row in BlacklistRepository.get_all_active(_db):
                alert_mgr.add_to_blacklist(row.ip_address)
            for code in GeoBlockRepository.get_active_codes(_db):
                alert_mgr.add_geo_block(code)
            for code in GeoAllowRepository.get_active_codes(_db):
                alert_mgr.add_geo_allow(code)
            for code in GeoWatchRepository.get_active_codes(_db):
                alert_mgr.add_geo_watch(code)
            logger.info("Synced whitelist/blacklist/geoblock into AlertManager")
        finally:
            _db.close()
    except Exception as e:
        logger.warning(f"Could not sync security lists: {e}")

    # Start thread-safe WebSocket alert consumer (async event loop)
    bridge = get_broadcast_bridge()
    get_alert_manager().set_broadcast_bridge(bridge)
    await bridge.start()
    logger.info("Alert broadcast bridge consumer running")

    # Lưu reference đến main event loop cho email service (thread-safe dispatch)
    from backend.notifications.email import email_service
    from backend.notifications.telegram import telegram_service
    from backend.notifications.discord import discord_service
    email_service.set_event_loop(asyncio.get_running_loop())
    telegram_service.set_event_loop(asyncio.get_running_loop())
    discord_service.set_event_loop(asyncio.get_running_loop())
    logger.info("Notification services event loops set.")

    # Start background cleanup worker cho Firewall (FR03)
    cleanup_task = asyncio.create_task(cleanup_expired_blacklist_task(interval_seconds=60))
    logger.info("Firewall cleanup worker started.")

    # Start background worker cho Server Status (FR02)
    server_status_task = asyncio.create_task(check_server_status_task())
    logger.info("Server status checker worker started.")

    # Start background worker cho UEBA (Hành vi người dùng)
    ueba_task = asyncio.create_task(ueba_detection_task(interval_seconds=60))
    logger.info("UEBA Detection worker started.")

    # Start log batch worker cho server agent logs
    from backend.api.routes.servers import start_log_worker
    await start_log_worker()
    logger.info("Server log batch worker started.")

    # Start security log cleanup task (dọn log cũ mỗi 6 giờ)
    from backend.database.security_log_store import log_cleanup_task
    log_cleanup = asyncio.create_task(log_cleanup_task(interval_hours=6, retention_days=7))
    logger.info("Security log cleanup task started.")

    # Start anomaly detection worker (học baseline + phát hiện bất thường)
    from backend.database.anomaly_worker import anomaly_detection_task
    anomaly_task = asyncio.create_task(anomaly_detection_task(interval_seconds=30))
    logger.info("Anomaly detection worker started.")

    # (log batch worker và security log cleanup đã được khởi động ở trên)

    # Start LogScanner for SSH brute-force detection (optional, env-gated)
    log_scanner = None
    if app_settings.enable_log_scanner:
        try:
            from backend.scripts.log_scanner import LogScanner
            log_scanner = LogScanner(get_alert_manager())
            if log_scanner._check_log_file_access():
                log_scanner.start()
                logger.info("LogScanner started.")
            else:
                log_scanner = None
                logger.warning("LogScanner disabled — cannot read auth log file.")
        except Exception as e:
            logger.warning("Could not start LogScanner: %s", e)

    yield

    # Shutdown: Cleanup
    logger.info("Shutting down IDS Backend...")

    # Stop firewall cleanup task
    cleanup_task.cancel()

    # Stop server status checker task
    server_status_task.cancel()

    # Stop UEBA task
    ueba_task.cancel()

    # Stop log batch worker
    from backend.api.routes.servers import stop_log_worker
    await stop_log_worker()

    # Stop security log cleanup task
    log_cleanup.cancel()

    # Stop anomaly detection worker
    anomaly_task.cancel()

    # (stop_log_worker đã được gọi ở trên)

    if log_scanner is not None:
        log_scanner.stop()
        log_scanner.join(timeout=5)

    # Stop pipeline if running
    if sniffer_routes.pipeline_coordinator and sniffer_routes.pipeline_coordinator.is_running:
        sniffer_routes.pipeline_coordinator.stop()

    if sniffer_routes.pipeline_task:
        sniffer_routes.pipeline_task.cancel()
        try:
            await sniffer_routes.pipeline_task
        except asyncio.CancelledError:
            pass

    # Stop alert broadcast consumer and drain queue
    await bridge.stop()


# Create FastAPI app
from backend.config import get_settings
try:
    settings = get_settings()
except RuntimeError as e:
    import sys
    logger.critical(str(e))
    sys.exit(1)

app = FastAPI(
    title="IDS Backend API",
    description="Machine Learning-based Intrusion Detection System Backend",
    version="1.0.0",
    lifespan=lifespan,
    max_request_size=settings.max_request_size
)

# Configure CORS
_cors_origins = settings.cors_origins
if not _cors_origins:
    import sys
    logger.critical("[PRODUCTION] CORS_ORIGINS is empty — refusing to start")
    sys.exit(1)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True, # Bắt buộc phải là True
    allow_methods=["*"],
    allow_headers=["Content-Type", "Set-Cookie", "X-API-Key", "X-CSRF-Token", "Authorization"],
)
logger.info("CORS origins: %s (environment=%s)", _cors_origins, settings.environment)

# Rate limiting (sliding window, in-memory, per client IP)
from backend.api.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from backend.api.routes import sniffer as sniffer_routes
    from backend.demo.attack_replay import get_attack_replay_demo

    coordinator = sniffer_routes.pipeline_coordinator
    is_demo_running = get_attack_replay_demo().is_running

    return {
        "status": "healthy",
        "service": "IDS Backend",
        "version": "1.0.0",
        "pipeline_running": (coordinator.is_running if coordinator else False) or is_demo_running,
    }


@app.get("/health/detailed")
async def health_detailed():
    """Detailed health check — connectivity status for all backing services."""
    from datetime import datetime, timezone
    from backend.api.routes import sniffer as sniffer_routes
    import sqlalchemy
    from backend.database.connection import engine
    from backend.cache.redis_cache import get_cache
    from backend.detection_engine.model_loader import get_model_loader
    from backend.demo.attack_replay import get_attack_replay_demo

    # PostgreSQL
    postgres_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        postgres_ok = True
    except Exception:
        pass

    # Cache (In-Memory)
    cache_ok = False
    try:
        cache_ok = get_cache().is_connected()
    except Exception:
        pass

    # Model
    model_loaded = False
    try:
        model_loaded = bool(get_model_loader().is_loaded)
    except Exception:
        pass

    coordinator = sniffer_routes.pipeline_coordinator
    is_demo_running = get_attack_replay_demo().is_running

    return {
        "postgres": {"connected": postgres_ok},
        "cache": {"connected": cache_ok},
        "model_loaded": model_loaded,
        "pipeline_running": (coordinator.is_running if coordinator else False) or is_demo_running,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    from backend.monitoring.metrics import metrics_endpoint
    return metrics_endpoint()


# Include routers
from backend.api.routes.security import (
    blacklist_router, geoblock_router, geoallow_router, geowatch_router, reports_router,
)
from backend.api.routes.logs import logs_router
from backend.api.routes.audit import audit_router
from backend.api.routes.geoip import geoip_router
from backend.api.legacy_routes import (
    alerts_router,
    predictions_router,
    models_router,
    whitelist_router,
    stats_router
)
from backend.api.routes.traffic import traffic_router
from backend.api.routes.sniffer import sniffer_router
from backend.api.routes.xai import xai_router
from backend.api.routes.demo import demo_router
from backend.api.routes.servers import router as servers_router
from backend.api.auth import auth_router
from backend.database.settings import router as settings_router
from backend.alert_engine.firewall import router as firewall_router

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(alerts_router, prefix="/api/alerts", tags=["alerts"])
app.include_router(predictions_router, prefix="/api/predictions", tags=["predictions"])
app.include_router(models_router, prefix="/api/models", tags=["models"])
app.include_router(whitelist_router, prefix="/api/whitelist", tags=["whitelist"])
app.include_router(blacklist_router, prefix="/api/blacklist", tags=["blacklist"])
app.include_router(geoblock_router, prefix="/api/geoblock", tags=["geoblock"])
app.include_router(geoallow_router, prefix="/api/geoallow", tags=["geoallow"])
app.include_router(geowatch_router, prefix="/api/geowatch", tags=["geowatch"])
app.include_router(geoip_router, prefix="/api/geoip", tags=["geoip"])
app.include_router(logs_router, prefix="/api/logs", tags=["logs"])
app.include_router(audit_router, prefix="/api/audit", tags=["audit"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
app.include_router(stats_router, prefix="/api/stats", tags=["statistics"])
app.include_router(sniffer_router, prefix="/api/sniffer", tags=["sniffer"])
app.include_router(traffic_router, prefix="/api/traffic", tags=["traffic"])
app.include_router(xai_router, prefix="/api/xai", tags=["xai"])
app.include_router(servers_router)
app.include_router(demo_router, prefix="/api/demo", tags=["demo"])
app.include_router(settings_router)
app.include_router(firewall_router)


# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time alert updates"""
    from backend.api.websocket import manager

    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"Received: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
