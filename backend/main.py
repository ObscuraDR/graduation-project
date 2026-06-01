"""
IDS Backend - Main Application
Machine Learning-based Intrusion Detection System
"""

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

    logger.info("Starting IDS Backend...")

    # Startup: Initialize databases
    from backend.database.connection import init_db
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

    # Start thread-safe WebSocket alert consumer (async event loop)
    bridge = get_broadcast_bridge()
    get_alert_manager().set_broadcast_bridge(bridge)
    await bridge.start()
    logger.info("Alert broadcast bridge consumer running")

    # Lưu reference đến main event loop cho email service (thread-safe dispatch)
    from backend.notifications.email import email_service
    email_service.set_event_loop(asyncio.get_running_loop())

    yield

    # Shutdown: Cleanup
    logger.info("Shutting down IDS Backend...")

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

    coordinator = sniffer_routes.pipeline_coordinator
    return {
        "status": "healthy",
        "service": "IDS Backend",
        "version": "1.0.0",
        "pipeline_running": coordinator.is_running if coordinator else False,
    }


@app.get("/health/detailed")
async def health_detailed():
    """Detailed health check — connectivity status for all backing services."""
    from datetime import datetime, timezone
    from backend.api.routes import sniffer as sniffer_routes
    import sqlalchemy
    from backend.database.connection import engine, get_mongo_client
    from backend.cache.redis_cache import get_cache
    from backend.detection_engine.model_loader import get_model_loader

    # PostgreSQL
    postgres_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        postgres_ok = True
    except Exception:
        pass

    # Redis
    redis_ok = False
    try:
        redis_ok = get_cache().is_connected()
    except Exception:
        pass

    # MongoDB
    mongo_ok = False
    try:
        get_mongo_client().admin.command("ping")
        mongo_ok = True
    except Exception:
        pass

    # Model
    model_loaded = False
    try:
        model_loaded = bool(get_model_loader().is_loaded)
    except Exception:
        pass

    coordinator = sniffer_routes.pipeline_coordinator
    return {
        "postgres": {"connected": postgres_ok},
        "redis": {"connected": redis_ok},
        "mongo": {"connected": mongo_ok},
        "model_loaded": model_loaded,
        "pipeline_running": coordinator.is_running if coordinator else False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    from backend.monitoring.metrics import metrics_endpoint
    return metrics_endpoint()


# Include routers
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
from backend.api.auth import auth_router

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(alerts_router, prefix="/api/alerts", tags=["alerts"])
app.include_router(predictions_router, prefix="/api/predictions", tags=["predictions"])
app.include_router(models_router, prefix="/api/models", tags=["models"])
app.include_router(whitelist_router, prefix="/api/whitelist", tags=["whitelist"])
app.include_router(stats_router, prefix="/api/stats", tags=["statistics"])
app.include_router(sniffer_router, prefix="/api/sniffer", tags=["sniffer"])
app.include_router(traffic_router, prefix="/api/traffic", tags=["traffic"])
app.include_router(xai_router, prefix="/api/xai", tags=["xai"])


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
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
