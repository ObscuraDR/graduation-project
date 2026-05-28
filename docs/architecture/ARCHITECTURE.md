# IDS Backend — System Architecture

This document describes the **Machine Learning-based Intrusion Detection System (IDS) backend** as implemented in this repository. All paths, modules, and behaviors refer to the real codebase at the project root.

---

## 1. Overview

The IDS backend is a **modular monolith** built on **FastAPI** and **Uvicorn**. It exposes REST APIs, a WebSocket channel for live alerts, health/metrics endpoints, and an optional **real-time packet-processing pipeline** driven by **Scapy**.

| Concern | Technology | Primary modules |
|---------|------------|-----------------|
| HTTP API | FastAPI 0.104, Uvicorn | `backend/main.py`, `backend/api/` |
| Real-time IDS | Scapy + asyncio | `backend/pipeline/coordinator.py`, `backend/capture_engine/` |
| ML inference | scikit-learn / joblib (+ optional TensorFlow) | `backend/detection_engine/`, `models/` |
| OLTP | PostgreSQL, SQLAlchemy 2.x | `backend/database/` |
| Document logs | MongoDB | `backend/database/mongo_logger.py` |
| Cooldown / cache | Redis | `backend/cache/redis_cache.py` |
| Config | pydantic-settings | `backend/config.py`, `.env` |

**Entry point (production):**

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**Alternate entry (CLI sniffer, no FastAPI):**

```bash
python backend/scripts/run_sniffer.py --interface eth0 --duration 60
```

---

## 2. Layered design

```
┌─────────────────────────────────────────────────────────────────┐
│  Presentation / API Layer                                        │
│  main.py, api/legacy_routes.py, api/routes/{sniffer,traffic,xai} │
│  api/websocket.py, api/middleware/rate_limit.py                  │
│  api/dependencies.py (API key)                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Application / Orchestration                                     │
│  pipeline/coordinator.py — wires capture → ML → alerts           │
│  alert_engine/alert_manager.py                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Domain Processing                                               │
│  capture_engine/packet_sniffer.py                                │
│  flow_engine/flow_builder.py                                     │
│  feature_engine/feature_extractor.py                             │
│  detection_engine/{model_loader,predictor}.py                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Infrastructure                                                  │
│  database/{connection,models,repository,mongo_logger}.py       │
│  cache/redis_cache.py, notifications/email.py                  │
│  monitoring/metrics.py, config.py                                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Offline ML (separate process; not in request hot path)          │
│  ml/{training,train_flow_model,models,xai,lstm_model,...}.py     │
│  scripts/preprocess_cicids2017.py, scripts/*.ps1                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Thread and asyncio model

The system mixes **three execution contexts**:

| Context | Where | What runs |
|---------|-------|-----------|
| **Main asyncio loop** | Uvicorn / FastAPI | HTTP handlers, WebSocket, `AlertBroadcastBridge._consume_loop` |
| **Pipeline asyncio task** | `asyncio.create_task(pipeline_coordinator.start())` | `while is_running: await asyncio.sleep(1)` — keeps task alive |
| **Scapy daemon thread** | `PacketSniffer._run_sniffer` | Blocking `scapy.sniff(..., prn=callback)` |

**Critical rule:** The sniffer thread must **never** call async WebSocket methods directly. Alerts use `AlertBroadcastBridge.enqueue_alert()` → `queue.Queue` → asyncio consumer → `ConnectionManager.broadcast()`.

```
  [Scapy Thread]                    [Asyncio Event Loop]
       │                                    │
       │ packet_callback()                  │
       │ (sync)                             │
       ├──────────────────────────────────────┤
       │ alert_manager.generate_alert()       │
       │   └─ broadcast_bridge.enqueue_alert()│
       │         (put_nowait on Queue)        │
       │                                    ├─ bridge._consume_loop()
       │                                    │    asyncio.to_thread(queue.get)
       │                                    │    await manager.broadcast()
       │                                    └─ WebSocket clients
```

**Email note:** `AlertManager.generate_alert()` calls `email_service.dispatch_alert_email()` from the **sniffer thread**. `EmailNotificationService` documents that `dispatch_alert_email` expects a running event loop (`asyncio.get_event_loop().create_task`). From the sniffer thread this may log *"No event loop running; email not dispatched"* — see `docs/TROUBLESHOOTING.md`.

---

## 4. Startup lifecycle

### 4.1 Module import phase (`backend/main.py`)

1. Create `logs/` and configure **JSON logging** (`pythonjsonlogger`) to `logs/backend.log` and stdout.
2. `get_settings()` from `backend/config.py` — **exits process** on production misconfiguration (`RuntimeError`).
3. Construct `FastAPI` with `lifespan`, `max_request_size=settings.max_request_size`.
4. **CORS:** `CORSMiddleware`; if `cors_origins` is empty → **exit** (production has no default origins).
5. Register `RateLimitMiddleware`.
6. Mount routers and define inline routes (`/health`, `/health/detailed`, `/metrics`, `/ws`).

### 4.2 Lifespan startup

```python
# backend/main.py — lifespan()
init_db()                              # backend/database/connection.py
bridge = get_broadcast_bridge()        # backend/api/websocket.py
get_alert_manager().set_broadcast_bridge(bridge)
await bridge.start()                   # starts alert-broadcast-consumer task
```

`init_db()` calls `Base.metadata.create_all(bind=engine)`. Alternatively, use `alembic upgrade head` for migration-based schema management. Failures are **logged** but do not abort startup.

### 4.3 Pipeline start (on demand)

Triggered only by `POST /api/sniffer/start` (`backend/api/routes/sniffer.py`):

1. API key validation (router-level `Depends(verify_api_key)`).
2. Interface validation (`require_valid_interface` + `validate_interface` from Scapy).
3. `get_coordinator(...)` + `set_broadcast_bridge`.
4. `asyncio.create_task(pipeline_coordinator.start())` → `initialize()` → `sniffer.start()` (thread).

### 4.4 Lifespan shutdown

1. Stop `pipeline_coordinator` if running.
2. Cancel `pipeline_task`.
3. `await bridge.stop()` — sentinel on queue, drain, cancel consumer.

---

## 5. Singleton and shared state

Global singletons use module-level `_instance` + `get_*()` factories:

| Factory | Module | Shared state |
|---------|--------|--------------|
| `get_settings()` | `config.py` | `@lru_cache` Settings |
| `get_sniffer()` | `capture_engine/packet_sniffer.py` | One `PacketSniffer` |
| `get_flow_builder()` | `flow_engine/flow_builder.py` | In-memory `flows` dict |
| `get_model_loader()` | `detection_engine/model_loader.py` | Loaded model/scaler/encoder |
| `get_predictor()` | `detection_engine/predictor.py` | Inference stats |
| `get_alert_manager()` | `alert_engine/alert_manager.py` | Cooldown, correlation, whitelist |
| `get_coordinator()` | `pipeline/coordinator.py` | Pipeline config + stats |
| `get_broadcast_bridge()` | `api/websocket.py` | `manager` + `broadcast_bridge` |
| `get_cache()` | `cache/redis_cache.py` | Redis client wrapper |

**Implications:**

- Restarting the sniffer with new parameters **mutates** the existing coordinator/sniffer singleton fields (`get_coordinator` updates in place).
- `FlowBuilder` flows are **process-local**; not shared across workers.
- **Multiple Uvicorn workers** would duplicate singletons and break pipeline/WebSocket coherence — **single worker recommended** for capture deployments.

**Sniffer route module globals** (`backend/api/routes/sniffer.py`):

```python
pipeline_task: Optional[asyncio.Task] = None
pipeline_coordinator = None
```

Used by `main.py` lifespan for coordinated shutdown.

---

## 6. Service interaction diagram

```
                         ┌──────────────┐
                         │   Clients    │
                         └──────┬───────┘
                REST /api/*     │     WS /ws
                                │
                   ┌────────────▼────────────┐
                   │   FastAPI (main.py)     │
                   │ CORS + RateLimit + Auth │
                   └───┬─────────┬──────┬───┘
                       │         │      │
          ┌────────────▼─┐  ┌────▼────┐ │
          │ legacy_routes │  │ sniffer │ │
          │ traffic, xai  │  │ routes  │ │
          └───────┬───────┘  └────┬────┘ │
                  │               │      │
                  │        ┌──────▼──────▼──────┐
                  │        │ PipelineCoordinator │
                  │        │ + PacketSniffer thr │
                  │        └──────┬──────────────┘
                  │               │
         ┌────────▼────────┐      │
         │  PostgreSQL     │◄─────┤ AlertManager, repos
         │  (SQLAlchemy)   │      │
         └────────┬────────┘      │
                  │         ┌─────▼─────┐
         ┌────────▼────────┐│  Redis    │ alert_cooldown:{ip}
         │  MongoDB        │└───────────┘
         │  flow_logs      │
         └─────────────────┘
                  │
         ┌────────▼────────┐
         │ models/*.pkl    │  (runtime artifacts; not in git)
         └─────────────────┘
```

---

## 7. Runtime dependency graph

Directed import graph for the **hot path** (simplified):

```
main.py
├── config
├── api.middleware.rate_limit
├── api.legacy_routes → database.connection, models, alert_manager, ml.models
├── api.routes.sniffer → dependencies, validation, pipeline, websocket, alert_manager
├── api.routes.traffic → flow_builder, pipeline (lazy)
├── api.routes.xai → predictor (FeatureContractError), ml.xai
└── lifespan → database.connection.init_db, websocket, alert_manager

pipeline/coordinator.py
├── capture_engine.packet_sniffer
├── flow_engine.flow_builder
├── feature_engine.feature_extractor
├── detection_engine.model_loader, predictor
├── alert_engine.alert_manager
├── database.connection, repository, mongo_logger
└── config.settings

alert_manager.py
├── database.connection, repository
├── notifications.email
└── cache.redis_cache
```

**Offline / broken path:**

- `backend/ml/inference.py` imports `backend.alerts.engine.AlertEngine` — **module does not exist** (replaced by `alert_engine/alert_manager.py` per comment in `legacy_routes.py`).

---

## 8. Critical services and failure modes

| Service | Module | If unavailable |
|---------|--------|----------------|
| PostgreSQL | `database/connection.py` | Alert/flow persistence fails; legacy APIs error |
| Model files | `models/{name}.pkl` | `PipelineCoordinator.initialize()` raises |
| Scapy / Npcap | `capture_engine/packet_sniffer.py` | No capture; PermissionError on Windows |
| Redis | `cache/redis_cache.py` | Cooldown falls back to in-memory dict |
| MongoDB | `mongo_logger.py` | Attack flow logs skipped (warning) |
| WebSocket bridge | `api/websocket.py` | Alerts still in DB; no live push |

---

## 9. Configuration system

Settings are defined in `backend/config.py` as class `Settings(BaseSettings)` with `env_file = ".env"`. Access via `get_settings()` (cached).

Production validator (`validate_production_secrets`) blocks startup when:

- `SECRET_KEY` or `API_KEY` are defaults
- Key lengths insufficient
- `CORS_ORIGINS` empty

See `docs/DEPLOYMENT_GUIDE.md` and `.env.example` for the full variable list.

---

## 10. Security architecture (summary)

| Control | Location | Scope |
|---------|----------|-------|
| API key (`X-API-Key`) | `api/dependencies.py` | `/api/sniffer/*` only |
| Rate limiting | `api/middleware/rate_limit.py` | `/api/sniffer/`, `/api/whitelist/`, `/api/xai/` |
| CORS | `main.py` | All routes |
| Input validation | `api/validation.py` | Sniffer interface, whitelist IPs |
| Request size | FastAPI `max_request_size` | Global |

**JWT** fields exist in `config.py` but **no JWT middleware or login routes** are implemented. `users` table is seeded by `init_db.py` only.

Full detail: `docs/SECURITY_MODEL.md`.

---

## 11. Deployment topology

Docker Compose (`docker-compose.yml`) defines:

- `ids-backend` — built from `Dockerfile`, port 8000, `NET_RAW` + `privileged`
- `postgres`, `mongodb`, `redis`
- `dashboard` — React frontend built from `frontend/Dockerfile`, port 3000
- `nginx` — references `./nginx/nginx.conf` (optional, for TLS termination)

See `docs/DEPLOYMENT_GUIDE.md`.

---

## 12. Known architectural limitations

1. **Prometheus metrics** defined in `monitoring/metrics.py` but `track_*` helpers are **not called** from the pipeline.
2. **Open legacy APIs** — alerts, predictions, traffic, WebSocket without API key.
3. **Single-process singletons** — not safe for multi-worker capture without redesign.
4. **Trained models not in git** — only `models/features.json` is versioned.
5. **`backend/ml/inference.py`** — stale import to removed `backend.alerts.engine`.
6. **`init_db.py` seed** — typo `Whititelist` may break whitelist seeding (line 52).

---

## 13. Verification commands

```bash
# Health
curl http://localhost:8000/health

# Detailed backing services
curl http://localhost:8000/health/detailed

# OpenAPI schema
curl http://localhost:8000/openapi.json

# Config security (script)
python backend/scripts/verify_config_security.py

# List interfaces (host)
python backend/scripts/list_interfaces.py
```

---

## 14. Related documentation

| Document | Topic |
|----------|-------|
| `docs/PIPELINE_FLOW.md` | Real-time packet → alert flow |
| `docs/API_REFERENCE.md` | REST/WebSocket contracts |
| `docs/ML_PIPELINE.md` | Training and inference |
| `docs/DATABASE_SCHEMA.md` | Postgres, Mongo, Redis |
| `docs/SECURITY_MODEL.md` | Threat surface and gaps |
| `docs/DEPLOYMENT_GUIDE.md` | Docker and production |
| `docs/TROUBLESHOOTING.md` | Operational failures |
