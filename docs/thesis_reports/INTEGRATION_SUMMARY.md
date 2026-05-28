# Z-Sentinel IDS — Integration Summary

Tài liệu này tóm tắt kiến trúc tích hợp hiện tại của hệ thống, các thành phần đã được kết nối, và trạng thái hoạt động.

---

## Tổng quan kiến trúc

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Z-Sentinel IDS Backend (FastAPI)                 │
│                                                                     │
│  ┌──────────────┐   ┌─────────────┐   ┌──────────────────────────┐ │
│  │ capture_     │   │ flow_engine │   │ feature_engine           │ │
│  │ engine       │──▶│ FlowBuilder │──▶│ FeatureExtractor         │ │
│  │ PacketSniffer│   │ (5-tuple    │   │ (20 statistical          │ │
│  │ (Scapy/Npcap)│   │  flows)     │   │  features)               │ │
│  └──────────────┘   └─────────────┘   └──────────┬───────────────┘ │
│                                                   │                 │
│  ┌────────────────────────────────────────────────▼───────────────┐ │
│  │ detection_engine                                               │ │
│  │  ModelLoader  (ensemble.pkl + scaler + encoder)                │ │
│  │  Predictor    (feature contract → StandardScaler → RF → label) │ │
│  └────────────────────────────────────────────────┬──────────────┘ │
│                                                   │                 │
│  ┌────────────────────────────────────────────────▼───────────────┐ │
│  │ alert_engine  AlertManager                                     │ │
│  │  • Gate 1: attack_type == "Normal" → suppress                  │ │
│  │  • Gate 2: confidence < 0.75 → suppress                       │ │
│  │  • Gate 3: src_ip in whitelist → suppress                      │ │
│  │  • Gate 4: Redis TTL cooldown → suppress                       │ │
│  │  • Correlation: severity escalation per-IP window              │ │
│  └──────┬──────────────────┬──────────────────────┬──────────────┘ │
│         │                  │                      │                 │
│  ┌──────▼──────┐  ┌────────▼──────┐  ┌───────────▼──────────────┐ │
│  │ PostgreSQL  │  │ WebSocket     │  │ Email (aiosmtplib)       │ │
│  │ alerts,     │  │ AlertBroadcast│  │ severity high|critical   │ │
│  │ flows,      │  │ Bridge        │  │ confidence ≥ 0.85        │ │
│  │ features,   │  │ (queue.Queue) │  └──────────────────────────┘ │
│  │ whitelist   │  └───────────────┘                               │
│  └─────────────┘                                                   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ MongoDB (flow_logs) │ Redis (alert cooldown TTLs)           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ API Layer                                                   │   │
│  │  POST /api/sniffer/start|stop   GET /api/sniffer/status     │   │
│  │  GET  /api/alerts/              GET /api/traffic/stats      │   │
│  │  POST /api/whitelist/add|remove GET /api/whitelist/list     │   │
│  │  POST /api/xai/explain          GET /health/detailed        │   │
│  │  WS   /ws                       GET /metrics                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Security Middleware                                         │   │
│  │  X-API-Key auth │ Sliding-window rate limiter │ Input valid │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Cấu trúc file hiện tại

```
graduation project/
├── backend/
│   ├── main.py                          ✅ FastAPI app, lifespan, routers, middleware
│   ├── config.py                        ✅ Pydantic Settings, production validation
│   ├── api/
│   │   ├── dependencies.py              ✅ verify_api_key (secrets.compare_digest)
│   │   ├── validation.py                ✅ IPv4, port, protocol, interface validators
│   │   ├── legacy_routes.py             ✅ alerts CRUD, predictions, models, whitelist, stats
│   │   ├── websocket.py                 ✅ ConnectionManager + AlertBroadcastBridge
│   │   ├── middleware/
│   │   │   └── rate_limit.py            ✅ Sliding-window per-IP rate limiter
│   │   └── routes/
│   │       ├── sniffer.py               ✅ POST /api/sniffer/start|stop, GET /status
│   │       ├── traffic.py               ✅ GET /api/traffic/* (read-only monitoring)
│   │       └── xai.py                   ✅ POST /api/xai/explain (SHAP)
│   ├── pipeline/
│   │   └── coordinator.py               ✅ PipelineCoordinator — wires all engines
│   ├── capture_engine/
│   │   └── packet_sniffer.py            ✅ Scapy sniff() daemon thread, dry-run mode
│   ├── flow_engine/
│   │   └── flow_builder.py              ✅ 5-tuple flows, inference gating (once/window)
│   ├── feature_engine/
│   │   └── feature_extractor.py         ✅ 20 statistical features
│   ├── detection_engine/
│   │   ├── model_loader.py              ✅ Load .pkl/.h5 + scaler + encoder
│   │   └── predictor.py                 ✅ Feature contract, NaN/Inf validation, inference
│   ├── alert_engine/
│   │   └── alert_manager.py             ✅ 4-gate suppression, correlation, severity escalation
│   ├── database/
│   │   ├── models.py                    ✅ SQLAlchemy ORM (TrafficFlow, FlowFeature, AttackAlert, etc.)
│   │   ├── connection.py                ✅ PostgreSQL engine, MongoDB client, Redis client
│   │   ├── repository.py                ✅ Repository pattern (CRUD operations)
│   │   ├── mongo_logger.py              ✅ MongoDB flow log writer (fire-and-forget)
│   │   └── init_db.py                   ✅ create_all() helper
│   ├── cache/
│   │   └── redis_cache.py               ✅ RedisCache + alert cooldown TTL helpers
│   ├── notifications/
│   │   └── email.py                     ✅ EmailNotificationService (aiosmtplib, async)
│   ├── monitoring/
│   │   └── metrics.py                   ✅ Prometheus metrics definitions
│   ├── ml/
│   │   ├── models.py                    ✅ IDSModel, RandomForestIDS, XGBoostIDS
│   │   ├── training.py                  ✅ CLI training script
│   │   ├── train_flow_model.py          ✅ CICIDS2017 training pipeline
│   │   ├── xai.py                       ✅ SHAP TreeExplainer wrapper
│   │   ├── create_dummy_models.py       ✅ Tạo model giả cho dev/demo
│   │   └── generate_training_data.py    ✅ Sinh dữ liệu training giả
│   └── tests/
│       ├── conftest.py                  ✅ Shared fixtures
│       ├── test_alerts.py               ✅ AlertManager unit tests
│       ├── test_api_security.py         ✅ API key auth + rate limiting
│       ├── test_db_integration.py       ✅ Repository layer (SQLite in-memory)
│       ├── test_email_alerts.py         ✅ Email gating (16 cases, no real SMTP)
│       ├── test_feature_contract.py     ✅ Feature vector alignment
│       └── test_health_detailed.py      ✅ Health check endpoints
├── models/
│   ├── features.json                    ✅ Feature contract (20 features, fixed order)
│   ├── ensemble.pkl                     (generated by create_dummy_models.py)
│   ├── ensemble_scaler.pkl              (generated)
│   ├── ensemble_encoder.pkl             (generated)
│   └── .gitkeep
├── scripts/
│   ├── list_interfaces.py               ✅ Liệt kê network interfaces
│   ├── validate_features.py             ✅ Validate features.json vs extractor
│   ├── test_predictor.py                ✅ Smoke-test model loading
│   ├── test_mongo_connection.py         ✅ Test MongoDB connection
│   ├── test_redis_connection.py         ✅ Test Redis connection
│   ├── preprocess_cicids2017.py         ✅ CICIDS2017 preprocessing
│   ├── demo_full.ps1                    ✅ Full demo automation (PowerShell)
│   └── demo_attack_simulation.ps1       ✅ Attack simulation instructions
├── docker-compose.yml                   ✅ PostgreSQL + MongoDB + Redis + Nginx + Dashboard
├── Dockerfile                           ✅ python:3.10-slim + libpcap-dev
├── requirements.txt                     ✅ Pinned versions
├── pytest.ini                           ✅ Test configuration
└── .env.example                         ✅ Template với tất cả biến
```

---

## Thread Model

```
┌─────────────────────────────────────────────────────────────────┐
│ Sniffer Thread (daemon)                                         │
│  scapy sniff() → _packet_handler() → packet_callback()         │
│  → FlowBuilder.add_packet()                                     │
│  → FeatureExtractor.extract_features()                          │
│  → Predictor.predict_flow()                                     │
│  → AlertManager.generate_alert()                                │
│      → AlertBroadcastBridge.enqueue_alert()  ──────────────┐   │
│      → SessionLocal() → PostgreSQL (DB writes)             │   │
│      → mongo_logger.log_flow_summary()                     │   │
└────────────────────────────────────────────────────────────│───┘
                                                             │
                                                    queue.Queue (thread-safe)
                                                             │
┌────────────────────────────────────────────────────────────▼───┐
│ asyncio Event Loop (main thread)                               │
│  AlertBroadcastBridge._consume_loop()                          │
│    asyncio.to_thread(queue.get, 0.25s)                         │
│    → ConnectionManager.broadcast()                             │
│    → websocket.send_text(json)  → Frontend Dashboard          │
│    → email_service.dispatch_alert_email()  → SMTP             │
│                                                                │
│  FastAPI HTTP handlers (all API endpoints)                     │
└────────────────────────────────────────────────────────────────┘
```

**Quy tắc quan trọng:**
- Sniffer thread → Event loop: chỉ qua `queue.Queue.put_nowait()` (thread-safe)
- Không bao giờ gọi `await` từ sniffer thread
- Không bao giờ gọi `asyncio.get_event_loop()` từ sniffer thread (deprecated Python 3.10+)

---

## Singleton Registry

Tất cả components là module-level singletons, khởi tạo lazy qua `get_*()` factories:

| Factory | Singleton | Khởi tạo khi |
|---|---|---|
| `get_sniffer()` | `PacketSniffer` | `pipeline.initialize()` |
| `get_flow_builder()` | `FlowBuilder` | `pipeline.initialize()` |
| `get_feature_extractor()` | `FeatureExtractor` | `pipeline.initialize()` |
| `get_model_loader()` | `ModelLoader` | `pipeline.initialize()` |
| `get_predictor()` | `Predictor` | `pipeline.initialize()` |
| `get_alert_manager()` | `AlertManager` | App startup (lifespan) |
| `get_cache()` | `RedisCache` | First use |
| `get_broadcast_bridge()` | `AlertBroadcastBridge` | App startup (lifespan) |
| `get_connection_manager()` | `ConnectionManager` | Module import |

---

## Startup Sequence

```
Uvicorn starts
    │
    ├─ main.py imports → get_settings() → validate config
    ├─ FastAPI app created
    ├─ Middleware registered (CORS, RateLimit)
    ├─ Routers registered
    │
    └─ lifespan startup:
        ├─ init_db() → PostgreSQL tables created
        ├─ get_broadcast_bridge() → AlertBroadcastBridge
        ├─ get_alert_manager() → AlertManager
        ├─ alert_manager.set_broadcast_bridge(bridge)
        └─ bridge.start() → asyncio.create_task(_consume_loop)
            │
            └─ App ready (accepting requests)
```

---

## Shutdown Sequence

```
SIGTERM received
    │
    └─ lifespan shutdown:
        ├─ pipeline_coordinator.stop() (nếu đang chạy)
        │   ├─ sniffer.stop() → join thread (5s timeout)
        │   └─ flow_builder.cleanup_expired_flows()
        ├─ pipeline_task.cancel()
        └─ bridge.stop()
            ├─ enqueue _SHUTDOWN_SENTINEL
            ├─ wait consumer task (3s timeout)
            └─ drain remaining queue
```

---

## Database Schema

### PostgreSQL Tables

| Table | Mô tả |
|---|---|
| `traffic_flows` | Network flows (5-tuple + stats) |
| `flow_features` | 20 ML features per flow |
| `attack_alerts` | Generated alerts với severity, confidence |
| `attack_history` | Per-IP attack history (count, severity distribution) |
| `models` | ML model metadata |
| `whitelist` | Whitelisted IPs/ports |
| `users` | User accounts (authentication) |
| `metrics` | Model performance metrics over time |

### MongoDB Collections

| Collection | Mô tả |
|---|---|
| `flow_logs` | Raw flow summaries (src/dst IPs, features, timestamp) |

### Redis Keys

| Key Pattern | TTL | Mô tả |
|---|---|---|
| `alert_cooldown:{ip}` | Configurable (default 30s) | Per-IP alert cooldown |

---

## Trạng thái tích hợp

| Component | Status | Ghi chú |
|---|---|---|
| PacketSniffer (Scapy) | ✅ Hoạt động | Cần Npcap trên Windows |
| FlowBuilder (5-tuple) | ✅ Hoạt động | In-memory dict |
| FeatureExtractor (20 features) | ✅ Hoạt động | Feature contract validated |
| ModelLoader (sklearn/TF) | ✅ Hoạt động | Cần model files trong `models/` |
| Predictor (inference) | ✅ Hoạt động | NaN/Inf validation |
| AlertManager (4-gate) | ✅ Hoạt động | Bug: NameError trong get_alert_history() |
| AlertBroadcastBridge | ✅ Hoạt động | Thread-safe queue → async broadcast |
| WebSocket (/ws) | ✅ Hoạt động | Không có authentication |
| PostgreSQL persistence | ✅ Hoạt động | Sync writes trên sniffer thread (known issue) |
| MongoDB logging | ✅ Hoạt động | Fire-and-forget, non-blocking |
| Redis cooldown | ✅ Hoạt động | In-memory fallback khi Redis down |
| Email notifications | ✅ Hoạt động | Async, severity+confidence gated |
| XAI (SHAP) | ✅ Hoạt động | Chỉ tree-based models |
| API Key auth | ✅ Hoạt động | timing-safe comparison |
| Rate limiting | ✅ Hoạt động | Sliding window per-IP |
| Input validation | ✅ Hoạt động | IPv4, port, protocol, interface |
| Prometheus metrics | ⚠️ Partial | Metrics defined nhưng chưa được increment |
| Alembic migrations | ✅ Hoạt động | `backend/alembic/versions/001_initial_schema.py` |

---

## Known Issues (xem ENGINEERING_REBUILD_GUIDE.md để biết chi tiết)

| ID | Vấn đề | Mức độ |
|---|---|---|
| C1 | Synchronous DB writes trên sniffer thread | Critical |
| C2 | Email dispatch từ sai thread context | Critical |
| C3 | Singleton mutation race trong get_coordinator() | Critical |
| C4 | flow_key UNIQUE constraint breaks window mode | Critical |
| C5 | NameError trong get_alert_history() | Critical |
| H1 | ~~Không có Alembic migrations~~ (đã fix) | ~~High~~ ✅ |
| H2 | privileged: true trong docker-compose.yml | High |
| H6 | FlowBuilder.flows dict không thread-safe | High |
| M1 | inter_arrival_times list tăng không giới hạn | Medium |

Xem [`ENGINEERING_REBUILD_GUIDE.md`](ENGINEERING_REBUILD_GUIDE.md) để biết phân tích đầy đủ và hướng dẫn fix.
