# Z-Sentinel IDS — Complete Engineering Rebuild Guide

> **Đối tượng đọc:** Developer muốn rebuild, maintain, refactor, debug, deploy, hoặc bảo vệ hệ thống này trong luận văn tốt nghiệp.  
> **Phạm vi:** Monolith-first, FastAPI, Docker Compose, single-worker, graduation-project scale.  
> **Không bao gồm:** Kubernetes, microservices, Kafka, CQRS, event sourcing.  
> **Ngôn ngữ:** Tiếng Anh cho thuật ngữ kỹ thuật, tiếng Việt cho giải thích.

---

## ⚡ Quick Start — Chạy hệ thống trong 5 phút

Nếu bạn chỉ muốn chạy được hệ thống ngay, làm đúng 4 bước này:

```bash
# Bước 1: Clone và cài dependencies
pip install -r requirements.txt

# Bước 2: Tạo dummy models (không cần dataset thật)
python backend/ml/create_dummy_models.py

# Bước 3: Start databases + backend
cp .env.example .env
docker compose up -d postgres mongodb redis
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Bước 4: Verify
curl http://localhost:8000/health/detailed
# Kết quả mong đợi: postgres/redis/mongo: connected: true, model_loaded: true
```

Sau khi backend chạy, start IDS pipeline:
```bash
# Windows: tìm tên interface trước
python backend/scripts/list_interfaces.py

# Start pipeline (thay Wi-Fi bằng tên interface của bạn)
curl -X POST "http://localhost:8000/api/sniffer/start?interface=Wi-Fi&model_name=ensemble" \
     -H "X-API-Key: changeme-set-API_KEY-in-env"
```

> **Lưu ý:** `API_KEY` mặc định trong `.env.example` là `changeme-set-API_KEY-in-env`. Thay bằng giá trị thực trong `.env`.

---

## 📋 Prerequisites — Bạn cần biết gì trước khi đọc guide này

### Kiến thức cần có

| Chủ đề | Mức độ cần | Tại sao cần |
|---|---|---|
| Python 3.10+ | Thành thạo | Toàn bộ backend viết bằng Python |
| FastAPI / Pydantic | Cơ bản | Framework chính, routing, validation |
| asyncio / async-await | Hiểu cơ bản | Event loop, WebSocket, async tasks |
| SQLAlchemy ORM | Cơ bản | Database models và queries |
| Docker / Docker Compose | Cơ bản | Deployment |
| Threading (Python) | Hiểu khái niệm | Sniffer chạy trên daemon thread riêng |
| Machine Learning (sklearn) | Biết khái niệm | Hiểu inference pipeline |

### Thuật ngữ quan trọng trong guide này

| Thuật ngữ | Giải thích |
|---|---|
| **5-tuple flow** | Một luồng mạng được định danh bởi 5 thông tin: src_ip, dst_ip, src_port, dst_port, protocol |
| **BPF filter** | Berkeley Packet Filter — cú pháp lọc gói tin của Scapy/tcpdump (ví dụ: `"tcp port 80"`) |
| **GIL** | Global Interpreter Lock — cơ chế của CPython, chỉ cho 1 thread chạy Python bytecode tại một thời điểm |
| **asyncio event loop** | Vòng lặp xử lý async của Python — chạy trên main thread, xử lý HTTP requests và WebSocket |
| **daemon thread** | Thread phụ tự động bị kill khi main thread kết thúc — sniffer chạy trên loại thread này |
| **singleton** | Pattern đảm bảo chỉ có 1 instance của một class trong toàn bộ process |
| **inference** | Quá trình dùng ML model đã train để dự đoán trên dữ liệu mới |
| **feature contract** | Thỏa thuận về tên và thứ tự của 20 features giữa training và inference |
| **cooldown** | Khoảng thời gian chờ trước khi sinh alert tiếp theo cho cùng một IP |
| **correlation** | Phân tích pattern tấn công từ cùng một IP để tăng severity |
| **backpressure** | Cơ chế xử lý khi producer tạo data nhanh hơn consumer xử lý được |

### Cấu trúc thư mục cần nắm trước

```
backend/
├── main.py                    ← Entry point, đọc file này đầu tiên
├── config.py                  ← Tất cả env vars, đọc thứ hai
├── pipeline/coordinator.py    ← "Bộ não" kết nối tất cả engines
├── capture_engine/            ← Bắt gói tin từ network
├── flow_engine/               ← Gom packets thành flows
├── feature_engine/            ← Tính 20 features từ flow
├── detection_engine/          ← Load model, chạy inference
├── alert_engine/              ← Sinh và quản lý alerts
├── api/                       ← HTTP endpoints, WebSocket, middleware
├── database/                  ← Models, repositories, connections
├── cache/                     ← Redis wrapper
└── notifications/             ← Email service
```

---

## Table of Contents

0. [Quick Start](#-quick-start--chạy-hệ-thống-trong-5-phút)
1. [Project Overview](#1-project-overview)
2. [Runtime Architecture](#2-runtime-architecture)
3. [Current Runtime Flow](#3-current-runtime-flow)
4. [Current Problems & Technical Debt](#4-current-problems--technical-debt)
5. [Module-by-Module Analysis](#5-module-by-module-analysis)
6. [Thread Ownership Model](#6-thread-ownership-model)
7. [WebSocket Architecture](#7-websocket-architecture)
8. [Alert Pipeline](#8-alert-pipeline)
9. [Persistence Pipeline](#9-persistence-pipeline)
10. [Queue & Backpressure Handling](#10-queue--backpressure-handling)
11. [Security Hardening](#11-security-hardening)
12. [Lifecycle Management](#12-lifecycle-management)
13. [Deployment Topology](#13-deployment-topology)
14. [Docker Compose Explanation](#14-docker-compose-explanation)
15. [Testing Strategy](#15-testing-strategy)
16. [Failure Recovery Strategy](#16-failure-recovery-strategy)
17. [Monitoring & Metrics Strategy](#17-monitoring--metrics-strategy)
18. [Performance Bottlenecks](#18-performance-bottlenecks)
19. [Concurrency Risks](#19-concurrency-risks)
20. [Refactor Roadmap](#20-refactor-roadmap)
21. [Incremental Migration Plan](#21-incremental-migration-plan)
22. [Production Recommendations](#22-production-recommendations)
23. [Graduation-Project Scope Decisions](#23-graduation-project-scope-decisions)

---

## 1. Project Overview

> 💡 **Đọc section này trước** — nó trả lời câu hỏi "hệ thống này làm gì và tại sao nó được thiết kế như vậy" trước khi đi vào chi tiết kỹ thuật.

### What the System Does

Z-Sentinel là một **hệ thống phát hiện xâm nhập mạng (IDS) thời gian thực dựa trên Machine Learning**. Hệ thống bắt gói tin mạng thô, gom chúng thành flows, trích xuất đặc trưng thống kê, chạy ML classifier đã train, và sinh cảnh báo bảo mật — tất cả trong một FastAPI process duy nhất.

Z-Sentinel is a **real-time, ML-based Network Intrusion Detection System (IDS)**. It captures live network packets, aggregates them into flows, extracts statistical features, runs a trained ML classifier, and generates security alerts — all in a single FastAPI process.

### Core Capabilities

| Capability | Implementation |
|---|---|
| Live packet capture | Scapy `sniff()` in a background daemon thread |
| Flow aggregation | 5-tuple (src_ip, dst_ip, src_port, dst_port, protocol) in-memory dict |
| Feature extraction | 20 statistical flow features (rates, flags, timing) |
| ML inference | scikit-learn / XGBoost / TensorFlow ensemble via joblib |
| Attack detection | Confidence-gated classification with severity scoring |
| Alert correlation | In-memory sliding-window pattern matching per source IP |
| Alert cooldown | Redis TTL keys (in-memory fallback) |
| Real-time push | WebSocket broadcast via thread-safe queue bridge |
| Persistence | PostgreSQL (flows, features, alerts) + MongoDB (raw flow logs) |
| Caching | Redis (alert cooldowns, optional query caching) |
| Email alerts | aiosmtplib async SMTP, severity/confidence gated |
| XAI | SHAP TreeExplainer on-demand via `/api/xai/explain` |
| Observability | Prometheus metrics at `/metrics`, structured JSON logs |
| API security | X-API-Key header auth + sliding-window rate limiting |

### Technology Stack

```
FastAPI 0.104  +  Uvicorn (single worker)
PostgreSQL 14  —  structured relational data (flows, alerts, models)
MongoDB 6      —  unstructured flow log documents
Redis 7        —  alert cooldown TTLs, optional caching
Scapy 2.5      —  raw packet capture (requires root / NET_RAW)
scikit-learn / XGBoost / TensorFlow  —  ML inference
SHAP           —  explainability
Docker Compose —  local + production deployment
```

---

## 2. Runtime Architecture

> 💡 **Điểm quan trọng nhất của section này:** Toàn bộ hệ thống chạy trong **một process duy nhất** với **hai execution context** — sniffer thread và asyncio event loop. Hiểu sự phân tách này là chìa khóa để debug mọi vấn đề trong dự án.

### High-Level Component Map

```mermaid
graph TD
    subgraph "Network Layer"
        NIC[Network Interface]
    end

    subgraph "Capture Thread (daemon)"
        SC[PacketSniffer\nScapy sniff()]
    end

    subgraph "FastAPI Process (main thread / event loop)"
        EL[asyncio Event Loop\nUvicorn single worker]
        PC[PipelineCoordinator\nasync start loop]
        FB[FlowBuilder\nin-memory dict]
        FE[FeatureExtractor\n20 features]
        PR[Predictor\nML inference]
        AM[AlertManager\ncooldown + correlation]
        BB[AlertBroadcastBridge\nqueue.Queue → asyncio]
        WS[ConnectionManager\nWebSocket clients]
        API[FastAPI Routers\nHTTP endpoints]
    end

    subgraph "Persistence Layer"
        PG[(PostgreSQL\nflows, alerts, features)]
        MG[(MongoDB\nflow_logs)]
        RD[(Redis\ncooldown TTLs)]
    end

    subgraph "External"
        FE_CLIENT[Frontend / Dashboard]
        EMAIL[SMTP Server]
    end

    NIC -->|raw packets| SC
    SC -->|packet_info dict\ncallback| PC
    PC --> FB
    FB -->|Flow object| FE
    FE -->|feature dict| PR
    PR -->|prediction dict| AM
    AM -->|enqueue_alert| BB
    BB -->|asyncio.to_thread| EL
    EL -->|broadcast| WS
    WS -->|JSON push| FE_CLIENT
    AM -->|SessionLocal| PG
    AM -->|log_flow_summary| MG
    AM -->|set_alert_cooldown| RD
    AM -->|dispatch_alert_email| EMAIL
    API -->|Depends(get_db)| PG
    API -->|get_flow_builder| FB
```

### Singleton Registry

> 💡 **Tại sao dùng singleton?** Vì toàn bộ pipeline chia sẻ state (flows, alerts, model). Nếu mỗi request tạo instance mới, chúng sẽ không thấy nhau. Singleton đảm bảo tất cả code đều trỏ đến cùng một FlowBuilder, cùng một AlertManager.

Every major component is a **module-level singleton** accessed via `get_*()` factory functions. This is the project's service container pattern.

```
get_sniffer()           → PacketSniffer
get_flow_builder()      → FlowBuilder
get_feature_extractor() → FeatureExtractor
get_model_loader()      → ModelLoader
get_predictor()         → Predictor
get_alert_manager()     → AlertManager
get_cache()             → RedisCache
get_broadcast_bridge()  → AlertBroadcastBridge
get_connection_manager()→ ConnectionManager
```

All singletons are initialized lazily on first call. This means the first HTTP request or pipeline start triggers initialization, not application startup.

---

## 3. Current Runtime Flow

> 💡 **Cách đọc section này:** Đọc theo thứ tự Startup → Pipeline Start → Per-Packet → Alert Broadcast → Shutdown. Đây là vòng đời đầy đủ của một alert từ lúc gói tin đến cho đến khi nó xuất hiện trên dashboard.

### Startup Sequence

```mermaid
sequenceDiagram
    participant UV as Uvicorn
    participant LF as lifespan()
    participant DB as init_db()
    participant BB as AlertBroadcastBridge
    participant AM as AlertManager

    UV->>LF: startup
    LF->>DB: create PostgreSQL tables
    LF->>BB: get_broadcast_bridge()
    LF->>AM: get_alert_manager()
    AM->>BB: set_broadcast_bridge(bridge)
    LF->>BB: bridge.start()
    Note over BB: asyncio.create_task(_consume_loop)
    LF-->>UV: yield (app ready)
```

### Pipeline Start (POST /api/sniffer/start)

```mermaid
sequenceDiagram
    participant CLI as HTTP Client
    participant SR as sniffer.py route
    participant PC as PipelineCoordinator
    participant ML as ModelLoader
    participant SN as PacketSniffer

    CLI->>SR: POST /api/sniffer/start?interface=eth0
    SR->>SR: verify_api_key
    SR->>SR: require_valid_interface (injection check)
    SR->>SR: hw_validate_interface (OS check)
    SR->>PC: get_coordinator(...)
    PC->>ML: model_loader.load_from_directory("ensemble")
    ML-->>PC: model loaded
    PC->>SN: sniffer.start()
    Note over SN: daemon thread spawned\nscapy sniff() blocking
    SR->>SR: asyncio.create_task(coordinator.start())
    Note over SR: coordinator.start() loops\nawait asyncio.sleep(1)
    SR-->>CLI: 200 {"status": "success"}
```

### Per-Packet Processing (hot path — sniffer thread)

```mermaid
sequenceDiagram
    participant SN as PacketSniffer\n(sniffer thread)
    participant PC as PipelineCoordinator\n(sniffer thread via callback)
    participant FB as FlowBuilder
    participant FE as FeatureExtractor
    participant PR as Predictor
    participant AM as AlertManager
    participant BB as AlertBroadcastBridge\n(thread-safe queue)

    SN->>PC: packet_callback(packet_info)
    PC->>FB: flow_builder.add_packet(packet_info)
    FB-->>PC: Flow object
    PC->>PC: _should_skip_inference(flow)
    alt skip (below min_packets or already processed)
        PC-->>SN: return
    else run inference
        PC->>FE: extract_features(flow)
        FE-->>PC: feature dict
        PC->>PR: predict_flow(flow)
        PR-->>PC: prediction dict
        PC->>PC: flow.mark_inference_complete()
        alt is_attack
            PC->>PC: _save_flow_to_db(flow, features)
            PC->>AM: generate_alert(prediction, flow_stats)
            AM->>AM: cooldown check (Redis / in-memory)
            AM->>AM: correlation + severity adjustment
            AM->>BB: enqueue_alert(alert)
            AM->>AM: _save_alert_to_db(alert)
            AM->>AM: _update_attack_history_db(...)
        end
    end
```

### Alert Broadcast (async consumer — event loop)

```mermaid
sequenceDiagram
    participant BB as AlertBroadcastBridge\n_consume_loop (async)
    participant TQ as queue.Queue
    participant CM as ConnectionManager
    participant WS as WebSocket Clients

    loop every 0.25s
        BB->>TQ: asyncio.to_thread(blocking_get, 0.25)
        TQ-->>BB: alert message dict
        BB->>CM: broadcast(message)
        CM->>WS: send_text(json)
    end
```

### Shutdown Sequence

```mermaid
sequenceDiagram
    participant UV as Uvicorn SIGTERM
    participant LF as lifespan() shutdown
    participant SR as sniffer_routes
    participant PC as PipelineCoordinator
    participant BB as AlertBroadcastBridge

    UV->>LF: shutdown signal
    LF->>SR: check pipeline_coordinator.is_running
    SR->>PC: coordinator.stop()
    PC->>PC: sniffer.stop() + flow cleanup
    LF->>SR: pipeline_task.cancel()
    LF->>BB: bridge.stop()
    BB->>BB: drain remaining queue
    BB-->>LF: done
```

---

## 4. Current Problems & Technical Debt

> ⚠️ **Section quan trọng nhất để đọc trước khi sửa code.** Mỗi vấn đề được phân loại theo mức độ rủi ro. Đọc hết section này trước khi chạm vào bất kỳ file nào.
>
> **Quy ước màu sắc:**
> - 🔴 **Critical** — có thể gây crash hoặc mất data trong production
> - 🟠 **High** — security risk hoặc behavioral bug cần fix trước demo
> - 🟡 **Medium** — memory leak hoặc correctness issue, fix trước thesis defense
> - 🟢 **Low** — code quality, fix khi có thời gian

This section is the most important for a rebuild. Every issue is classified by risk and impact.

### 4.1 Critical Issues (fix before production)

#### C1 — Synchronous DB writes on the sniffer thread

**File:** `pipeline/coordinator.py` → `_save_flow_to_db()`  
**File:** `alert_engine/alert_manager.py` → `_save_alert_to_db()`, `_update_attack_history_db()`

```python
# CURRENT — runs on sniffer thread, blocks packet processing
def _save_flow_to_db(self, flow, features):
    db = SessionLocal()   # ← synchronous SQLAlchemy
    try:
        TrafficFlowRepository.create_flow(db, flow_data)
        FlowFeatureRepository.create_feature(db, features, traffic_flow.id)
    finally:
        db.close()
```

**Problem:** Every detected attack causes a synchronous PostgreSQL write on the sniffer thread. This blocks `packet_callback()`, which means packets are dropped during high-traffic attack scenarios — exactly when you need the IDS most.

**Risk:** HIGH. Under a DDoS simulation, DB latency (even 5ms) multiplied by hundreds of alerts per second will cause the packet queue to fill and drop packets.

**Fix:** Enqueue DB writes to a separate `asyncio.Queue` and process them in a dedicated async task on the event loop. See Section 20 for implementation.

---

#### C2 — Email dispatch called from sniffer thread context

**File:** `alert_engine/alert_manager.py` → `generate_alert()`

```python
# CURRENT — called from sniffer thread
if self.enable_email:
    email_service.dispatch_alert_email(alert)  # calls asyncio.get_event_loop()
```

**File:** `notifications/email.py` → `dispatch_alert_email()`

```python
asyncio.get_event_loop().create_task(_send())  # ← UNSAFE from non-async thread
```

**Problem:** `asyncio.get_event_loop()` from a non-async thread is deprecated in Python 3.10+ and raises `DeprecationWarning`. In Python 3.12 it raises `RuntimeError` if there is no current event loop in the thread. The email task is created on the wrong loop reference.

**Fix:** Move email dispatch into the `AlertBroadcastBridge._dispatch()` coroutine, which already runs on the event loop. The bridge already receives every alert — just call `email_service.dispatch_alert_email(alert)` there.

---

#### C3 — Singleton mutation race condition in `get_coordinator()`

**File:** `pipeline/coordinator.py` → `get_coordinator()`

```python
# CURRENT — mutates existing singleton without lock
else:
    _coordinator_instance.interface = interface   # ← no lock
    _coordinator_instance.filter_expr = filter_expr
    ...
```

**Problem:** If two concurrent POST `/api/sniffer/start` requests arrive simultaneously, both can mutate the singleton's fields in an interleaved way, producing a coordinator with mixed configuration.

**Fix:** Add a simple `threading.Lock` around the singleton creation/mutation block, or better: reject the second request early (already done via `is_running` check, but the mutation path is still reachable if the coordinator exists but is stopped).

---

#### C4 — `flow_key` uniqueness constraint causes DB errors on flow re-use

**File:** `database/models.py` → `TrafficFlow`

```python
flow_key = Column(String(200), unique=True, nullable=False, index=True)
```

**File:** `database/repository.py` → `TrafficFlowRepository.create_flow()`

The `flow_key` is a 5-tuple string. In `window` prediction mode, the same flow can trigger multiple DB inserts (once per prediction interval). The second insert will raise `IntegrityError` because `flow_key` is UNIQUE.

**Problem:** The repository always calls `INSERT`, never `INSERT ... ON CONFLICT DO UPDATE`. In window mode this silently fails (exception is caught and logged), meaning only the first flow record is saved.

**Fix:** Use `INSERT ... ON CONFLICT (flow_key) DO UPDATE` (PostgreSQL upsert) or check-then-insert with proper error handling.

---

#### C5 — `alert_manager.get_alert_history()` has a NameError bug

**File:** `alert_engine/alert_manager.py`  
**Dòng cần sửa:** Tìm method `get_alert_history` (khoảng dòng 180)

```python
# TRƯỚC KHI SỬA — sẽ crash với NameError
def get_alert_history(self, ip_address: str) -> List[Dict]:
    if ip_address not in self.attack_patterns:
        return []
    return self.attack_patterns[src_ip]   # ← src_ip không tồn tại
```

```python
# SAU KHI SỬA
def get_alert_history(self, ip_address: str) -> List[Dict]:
    if ip_address not in self.attack_patterns:
        return []
    return self.attack_patterns[ip_address]   # ← đổi src_ip → ip_address
```

**Verify:** Sau khi sửa, chạy:
```python
from backend.alert_engine.alert_manager import get_alert_manager
am = get_alert_manager()
result = am.get_alert_history("10.0.0.1")
assert result == [], f"Expected [], got {result}"
print("✅ C5 fix verified")
```

---

### 4.2 High-Risk Issues (fix before demo)

#### H1 — ~~No database migration system~~ ✅ ĐÃ FIX

> ✅ **Đã fix:** Alembic đã được khởi tạo với migration đầu tiên tại `backend/alembic/versions/001_initial_schema.py`.

**Cách sử dụng Alembic cho schema changes:**

```bash
# Apply migrations
alembic upgrade head

# Tạo migration mới khi thay đổi models.py
alembic revision --autogenerate -m "description"
alembic upgrade head

# Xem migration history
alembic history --verbose
alembic current
```

---

#### H2 — `privileged: true` in Docker Compose

> 🟠 **Tại sao nguy hiểm?** `privileged: true` cho container quyền truy cập đầy đủ vào kernel của host — tương đương chạy root không có sandbox. Nếu container bị compromise, attacker có thể escape ra host machine.

**File:** `docker-compose.yml` — service `ids-backend`

```yaml
# TRƯỚC KHI SỬA — nguy hiểm
ids-backend:
  privileged: true        # ← XÓA DÒNG NÀY
  cap_add:
    - NET_RAW
    - NET_ADMIN
```

```yaml
# SAU KHI SỬA — chỉ cần 2 capabilities này
ids-backend:
  cap_add:
    - NET_RAW    # Scapy cần để mở raw socket
    - NET_ADMIN  # Cần để quản lý network interface
  # privileged: true đã bị xóa
```

**Verify:**
```bash
docker compose up -d ids-backend
docker inspect ids-backend | grep -i privileged
# Phải thấy: "Privileged": false

# Test packet capture vẫn hoạt động
curl -X POST "http://localhost:8000/api/sniffer/start?interface=eth0&dry_run=true" \
     -H "X-API-Key: your-key"
# Phải thấy: {"status": "success"}
```

---

#### H3 — Hardcoded credentials in docker-compose.yml

> 🟠 **Tại sao nguy hiểm?** Bất kỳ ai có quyền đọc repo (kể cả public GitHub) đều biết password database của bạn.

**File:** `docker-compose.yml`

```yaml
# TRƯỚC KHI SỬA — credentials hardcoded
postgres:
  environment:
    POSTGRES_PASSWORD: ids_password        # ← hardcoded

mongodb:
  environment:
    MONGO_INITDB_ROOT_PASSWORD: ids_mongo_pass  # ← hardcoded

redis:
  command: redis-server --requirepass ids_redis_pass  # ← hardcoded
```

```yaml
# SAU KHI SỬA — dùng env vars từ .env file
postgres:
  environment:
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}

mongodb:
  environment:
    MONGO_INITDB_ROOT_PASSWORD: ${MONGO_ROOT_PASSWORD}

redis:
  command: redis-server --requirepass ${REDIS_PASSWORD} --appendonly yes
```

**Thêm vào `.env` (file này đã có trong `.gitignore`):**
```ini
POSTGRES_PASSWORD=change-this-strong-password-123
MONGO_ROOT_PASSWORD=change-this-strong-password-456
REDIS_PASSWORD=change-this-strong-password-789
```

**Verify:**
```bash
# Kiểm tra .env không bị commit
git status .env
# Phải thấy: .env không xuất hiện (đã gitignored)

# Kiểm tra docker compose đọc được env vars
docker compose config | grep -i password
# Phải thấy giá trị từ .env, không phải hardcoded string
```

---

#### H4 — `api_reload: true` default in config

> 🟠 **Tại sao nguy hiểm?** Uvicorn `--reload` spawn một process con để watch file changes. Trong Docker với bind mount `./backend:/app/backend`, process con này liên tục scan files, gây CPU cao. Tệ hơn: khi reload xảy ra, tất cả singletons (FlowBuilder, AlertManager) bị khởi tạo lại — mất toàn bộ state đang chạy.

**File:** `backend/config.py`

```python
# TRƯỚC KHI SỬA
api_reload: bool = True   # ← mặc định bật reload
```

```python
# SAU KHI SỬA
api_reload: bool = False  # ← tắt mặc định, chỉ bật qua env var
```

**Để bật reload trong development, thêm vào `.env`:**
```ini
API_RELOAD=true
```

**Verify:**
```bash
# Kiểm tra uvicorn không chạy với --reload trong production
docker exec ids-backend ps aux | grep uvicorn
# Phải thấy: uvicorn backend.main:app --host 0.0.0.0 --port 8000
# KHÔNG thấy: --reload
```

---

#### H5 — MongoDB connection not closed on shutdown

> 🟠 **Tại sao nguy hiểm?** MongoDB connection pool không được đóng khi app shutdown. Sau nhiều lần restart (ví dụ trong CI/CD), connections tích lũy và có thể exhaust MongoDB connection limit.

**File:** `backend/main.py` → `lifespan()` shutdown section  
**File:** `backend/database/connection.py` → `close_connections()`

```python
# TRƯỚC KHI SỬA — lifespan shutdown trong main.py
    # Stop alert broadcast consumer and drain queue
    await bridge.stop()
    # ← MongoDB và Redis không được đóng
```

```python
# SAU KHI SỬA — thêm vào cuối lifespan shutdown
    # Stop alert broadcast consumer and drain queue
    await bridge.stop()

    # Close all database connections
    from backend.database.connection import close_connections
    close_connections()
    logger.info("All database connections closed")
```

**Và trong `database/connection.py`, hàm `close_connections()` đã có sẵn nhưng chưa đóng MongoDB đúng cách:**

```python
# TRƯỚC KHI SỬA
def close_connections():
    global _mongo_client, _redis_client
    if _mongo_client:
        _mongo_client.close()   # ← đã có
        logger.info("MongoDB connection closed")
    # ...
```

Hàm này đã đúng — vấn đề là nó chưa được gọi trong lifespan. Fix ở trên (thêm `close_connections()` vào lifespan) là đủ.

**Verify:**
```bash
# Restart backend nhiều lần
for i in 1 2 3; do docker compose restart ids-backend; sleep 3; done

# Kiểm tra MongoDB connections
docker exec ids-mongodb mongosh \
  --username ids_mongo_user --password ids_mongo_pass \
  --authenticationDatabase admin \
  --eval "db.serverStatus().connections"
# current connections phải ổn định, không tăng mỗi lần restart
```

---

#### H6 — `FlowBuilder.flows` dict is not thread-safe

> 🟠 **Tại sao nguy hiểm?** `add_packet()` chạy trên sniffer thread, `cleanup_expired_flows()` chạy trên cả sniffer thread VÀ HTTP request thread (khi gọi `POST /api/traffic/flows/cleanup`). Hai thread cùng mutate dict → `RuntimeError: dictionary changed size during iteration`.

**File:** `backend/flow_engine/flow_builder.py`

```python
# TRƯỚC KHI SỬA — không có lock
class FlowBuilder:
    def __init__(self, ...):
        self.flows: Dict[str, Flow] = {}
        # ← không có threading.Lock

    def add_packet(self, packet_info: dict) -> Optional[Flow]:
        # ...
        if flow_key in self.flows:          # ← đọc dict
            flow = self.flows[flow_key]
        else:
            flow = Flow(...)
            self.flows[flow_key] = flow     # ← ghi dict (không có lock)
        flow.add_packet(packet_info)
        return flow

    def cleanup_expired_flows(self) -> List[Flow]:
        # ...
        for flow_key, flow in self.flows.items():  # ← iterate dict
            # ...
        for key in expired_keys:
            del self.flows[key]             # ← xóa dict (không có lock)
```

```python
# SAU KHI SỬA — thêm threading.Lock
import threading

class FlowBuilder:
    def __init__(self, ...):
        self.flows: Dict[str, Flow] = {}
        self._lock = threading.Lock()       # ← thêm lock

    def add_packet(self, packet_info: dict) -> Optional[Flow]:
        src_ip = packet_info.get("src_ip")
        dst_ip = packet_info.get("dst_ip")
        if not src_ip or not dst_ip:
            logger.warning("Packet missing IP addresses")
            return None

        src_port = packet_info.get("src_port")
        dst_port = packet_info.get("dst_port")
        protocol = packet_info.get("protocol", "unknown")
        flow_key = self._generate_flow_key(src_ip, dst_ip, src_port, dst_port, protocol)

        with self._lock:                    # ← acquire lock trước khi đọc/ghi
            if flow_key in self.flows:
                flow = self.flows[flow_key]
            else:
                flow = Flow(src_ip, dst_ip, src_port, dst_port, protocol)
                self.flows[flow_key] = flow
                self.total_flows_created += 1
                logger.debug("Created new flow: %s", flow_key)

        flow.add_packet(packet_info)        # ← Flow.add_packet chỉ modify flow object
        return flow                         #   không cần lock vì flow chỉ có 1 owner

    def cleanup_expired_flows(self) -> List[Flow]:
        current_time = datetime.utcnow()
        removed_flows: List[Flow] = []
        expired_keys: List[str] = []

        with self._lock:                    # ← acquire lock cho toàn bộ cleanup
            for flow_key, flow in list(self.flows.items()):  # list() để copy keys
                inactive_sec = (current_time - flow.last_seen).total_seconds()
                age_sec = (current_time - flow.start_time).total_seconds()

                reason: Optional[str] = None
                if inactive_sec > self.flow_expire_sec:
                    reason = f"inactive {inactive_sec:.1f}s"
                elif age_sec > self.flow_max_lifetime_sec:
                    reason = f"max lifetime {age_sec:.1f}s"
                elif (
                    flow.processed
                    and flow.last_predicted_at is not None
                    and (current_time - flow.last_predicted_at).total_seconds()
                    > self.processed_flow_retention_sec
                ):
                    reason = "processed retention"
                    self.total_processed_flows_removed += 1

                if reason:
                    removed_flows.append(flow)
                    expired_keys.append(flow_key)
                    self.total_flows_expired += 1
                    logger.debug("Expired flow %s (%s)", flow_key, reason)

            for key in expired_keys:
                del self.flows[key]

        return removed_flows

    def get_active_flows(self) -> List[Flow]:
        with self._lock:                    # ← cũng cần lock khi đọc
            return list(self.flows.values())

    def get_stats(self) -> dict:
        with self._lock:
            active = len(self.flows)
            processed_active = sum(1 for f in self.flows.values() if f.processed)
        return {
            "active_flows": active,
            "processed_active_flows": processed_active,
            # ... rest of stats
        }
```

**Verify:**
```python
# test_thread_safety.py — chạy file này để verify
import threading
from backend.flow_engine.flow_builder import FlowBuilder

def test_concurrent_add_and_cleanup():
    fb = FlowBuilder(flow_expire_sec=1)
    errors = []

    def add_packets():
        for i in range(2000):
            try:
                fb.add_packet({
                    "src_ip": f"10.0.{i % 255}.{i % 100}",
                    "dst_ip": "192.168.1.1",
                    "src_port": 1024 + (i % 60000),
                    "dst_port": 80,
                    "protocol": "tcp",
                    "length": 100,
                })
            except Exception as e:
                errors.append(f"add_packet error: {e}")

    def cleanup_loop():
        import time
        for _ in range(50):
            try:
                fb.cleanup_expired_flows()
                time.sleep(0.01)
            except Exception as e:
                errors.append(f"cleanup error: {e}")

    threads = [threading.Thread(target=add_packets) for _ in range(4)]
    threads.append(threading.Thread(target=cleanup_loop))
    for t in threads: t.start()
    for t in threads: t.join()

    assert len(errors) == 0, f"Thread safety errors:\n" + "\n".join(errors)
    print("✅ H6 fix verified — no thread safety errors")

test_concurrent_add_and_cleanup()
```

---

### 4.3 Medium-Risk Issues (fix before thesis defense)

#### M1 — `inter_arrival_times` list grows unbounded

> 🟡 **Tại sao nguy hiểm?** Một TCP connection dài (ví dụ file transfer 10 phút) có thể có 100,000+ packets. List này lưu 100,000 floats = ~800KB chỉ cho một flow. Với 100 flows đồng thời = 80MB chỉ cho IAT data.

**File:** `backend/flow_engine/flow_builder.py` → class `Flow`

```python
# TRƯỚC KHI SỬA — list tăng không giới hạn
class Flow:
    def __init__(self, ...):
        self.inter_arrival_times: List[float] = []  # ← memory leak

    def add_packet(self, packet_info: dict) -> None:
        # ...
        if self.last_packet_time:
            inter_arrival = (self.last_seen - self.last_packet_time).total_seconds()
            self.inter_arrival_times.append(inter_arrival)  # ← append mãi mãi
        # ...

    def get_stats(self) -> dict:
        inter_arrival_mean = (
            sum(self.inter_arrival_times) / len(self.inter_arrival_times)
            if self.inter_arrival_times else 0
        )  # ← O(n) mỗi lần gọi
```

```python
# SAU KHI SỬA — dùng running mean, O(1) memory và O(1) time
class Flow:
    def __init__(self, ...):
        # Xóa: self.inter_arrival_times: List[float] = []
        self._iat_sum: float = 0.0    # ← tổng cộng dồn
        self._iat_count: int = 0      # ← số lượng samples

    def add_packet(self, packet_info: dict) -> None:
        # ...
        if self.last_packet_time:
            inter_arrival = (self.last_seen - self.last_packet_time).total_seconds()
            # Xóa: self.inter_arrival_times.append(inter_arrival)
            self._iat_sum += inter_arrival    # ← O(1) update
            self._iat_count += 1
        # ...

    def get_stats(self) -> dict:
        inter_arrival_mean = (
            self._iat_sum / self._iat_count
            if self._iat_count > 0 else 0.0
        )  # ← O(1) thay vì O(n)
        return {
            # ...
            "inter_arrival_time_mean": inter_arrival_mean,
            # ...
        }
```

**Verify:**
```python
from backend.flow_engine.flow_builder import Flow

flow = Flow("10.0.0.1", "192.168.1.1", 1234, 80, "tcp")
# Simulate 10,000 packets
import time
for i in range(10000):
    flow.add_packet({
        "src_ip": "10.0.0.1", "dst_ip": "192.168.1.1",
        "src_port": 1234, "dst_port": 80,
        "protocol": "tcp", "length": 100,
    })

# Kiểm tra không còn list
assert not hasattr(flow, 'inter_arrival_times'), "inter_arrival_times list still exists"
# Kiểm tra mean vẫn tính được
stats = flow.get_stats()
assert "inter_arrival_time_mean" in stats
print(f"✅ M1 fix verified — IAT mean: {stats['inter_arrival_time_mean']:.6f}s")
```

---

#### M2 — `attack_patterns` dict in AlertManager grows unbounded

> 🟡 **Tại sao nguy hiểm?** Mỗi IP tấn công tạo một entry trong dict. Sau 24h chạy liên tục với nhiều attacker IPs, dict này có thể chứa hàng nghìn entries với lists rỗng — pure memory waste.

**File:** `backend/alert_engine/alert_manager.py` → `_update_attack_patterns()`

```python
# TRƯỚC KHI SỬA — không prune keys rỗng
def _update_attack_patterns(self, src_ip, attack_type, alert):
    self.attack_patterns[src_ip].append(alert)

    current_time = datetime.utcnow()
    window_start = current_time - timedelta(seconds=self.correlation_window)

    self.attack_patterns[src_ip] = [
        a for a in self.attack_patterns[src_ip]
        if datetime.fromisoformat(a['timestamp']) >= window_start
    ]
    # ← nếu list rỗng sau cleanup, key vẫn tồn tại trong dict
```

```python
# SAU KHI SỬA — xóa key khi list rỗng
def _update_attack_patterns(self, src_ip, attack_type, alert):
    self.attack_patterns[src_ip].append(alert)

    current_time = datetime.utcnow()
    window_start = current_time - timedelta(seconds=self.correlation_window)

    self.attack_patterns[src_ip] = [
        a for a in self.attack_patterns[src_ip]
        if datetime.fromisoformat(a['timestamp']) >= window_start
    ]

    # ← thêm: xóa key nếu list rỗng
    if not self.attack_patterns[src_ip]:
        del self.attack_patterns[src_ip]
```

**Verify:**
```python
from backend.alert_engine.alert_manager import AlertManager
import time

am = AlertManager(correlation_window=1)  # 1 giây để test nhanh

# Simulate alert từ một IP
fake_alert = {
    "alert_id": "test-001", "attack_type": "DDoS",
    "timestamp": "2026-01-01T00:00:00",  # timestamp cũ, ngoài window
}
am.attack_patterns["10.0.0.1"].append(fake_alert)
am._update_attack_patterns("10.0.0.1", "DDoS", {
    "alert_id": "test-002", "attack_type": "DDoS",
    "timestamp": "2026-01-01T00:00:00",  # cũng cũ
})

# Sau khi update, key phải bị xóa vì tất cả entries đều ngoài window
assert "10.0.0.1" not in am.attack_patterns, "Key should be pruned"
print("✅ M2 fix verified — empty keys are pruned")
```

---

#### M3 — `_windows` dict in rate limiter grows unbounded

> 🟡 **Tại sao nguy hiểm?** Mỗi unique client IP tạo một entry. Trong một cuộc tấn công scan với 10,000 IPs khác nhau, dict này có 10,000 entries với deques rỗng — không bao giờ được dọn.

**File:** `backend/api/middleware/rate_limit.py` → `_is_rate_limited()`

```python
# TRƯỚC KHI SỬA — không xóa key khi deque rỗng
def _is_rate_limited(client_ip: str, path: str) -> Tuple[bool, int, int]:
    # ...
    with _lock:
        if key not in _windows:
            _windows[key] = deque()

        dq = _windows[key]

        cutoff = now - window
        while dq and dq[0] <= cutoff:
            dq.popleft()
        # ← nếu dq rỗng sau eviction, key vẫn tồn tại

        if len(dq) >= max_req:
            retry_after = int(window - (now - dq[0])) + 1
            return True, max_req, retry_after

        dq.append(now)
        return False, max_req, 0
```

```python
# SAU KHI SỬA — xóa key khi deque rỗng và không có request mới
def _is_rate_limited(client_ip: str, path: str) -> Tuple[bool, int, int]:
    rule = _get_limit(path)
    if rule is None:
        return False, 0, 0

    max_req, window = rule
    key = f"{client_ip}:{path.split('/')[2]}"
    now = time.monotonic()

    with _lock:
        if key not in _windows:
            _windows[key] = deque()

        dq = _windows[key]

        cutoff = now - window
        while dq and dq[0] <= cutoff:
            dq.popleft()

        if len(dq) >= max_req:
            retry_after = int(window - (now - dq[0])) + 1
            return True, max_req, retry_after

        dq.append(now)

        # ← thêm: nếu deque chỉ có 1 entry (vừa append), không cần cleanup
        # Cleanup chỉ khi deque rỗng sau eviction (không có request mới)
        # Điều này xảy ra ở lần gọi tiếp theo khi IP không còn active
        return False, max_req, 0


def _cleanup_stale_windows() -> int:
    """Xóa tất cả entries với deque rỗng. Gọi định kỳ hoặc từ test."""
    with _lock:
        stale = [k for k, dq in _windows.items() if not dq]
        for k in stale:
            del _windows[k]
    return len(stale)
```

**Verify:**
```python
from backend.api.middleware.rate_limit import _windows, _is_rate_limited, reset_all

reset_all()
# Simulate nhiều IPs khác nhau
for i in range(100):
    _is_rate_limited(f"10.0.{i}.1", "/api/sniffer/status")

print(f"Windows dict size: {len(_windows)}")  # 100 entries

# Sau khi window hết hạn (60s), entries sẽ bị evict
# Trong test, dùng cleanup function
from backend.api.middleware.rate_limit import _cleanup_stale_windows
# (sau khi window expire)
cleaned = _cleanup_stale_windows()
print(f"✅ M3 fix verified — cleaned {cleaned} stale entries")
```

---

#### M4 — Scaler applied twice during inference

> 🟡 **Tại sao nguy hiểm?** Nếu scaler được apply 2 lần, features bị transform sai hoàn toàn. Ví dụ: `packet_rate = 1000` → sau scale lần 1: `2.3` → sau scale lần 2: `-0.8`. Model nhận input sai → predictions vô nghĩa.

**File:** `backend/detection_engine/model_loader.py` → `predict()` và `predict_proba()`

Vấn đề: cả `predict()` và `predict_proba()` đều apply scaler riêng lẻ. Khi `predict_flow()` gọi cả hai, features bị scale 2 lần.

```python
# TRƯỚC KHI SỬA — scale trong cả predict() và predict_proba()
def predict(self, features: np.ndarray) -> np.ndarray:
    if self.scaler:
        features = self.scaler.transform(features)  # ← scale lần 1
    predicted_classes = self.model.predict(features)
    return predicted_classes

def predict_proba(self, features: np.ndarray) -> np.ndarray:
    if self.scaler:
        features = self.scaler.transform(features)  # ← scale lần 2 (WRONG)
    probabilities = self.model.predict_proba(features)
    return probabilities
```

```python
# SAU KHI SỬA — thêm method _apply_scaler() dùng chung
def _apply_scaler(self, features: np.ndarray) -> np.ndarray:
    """Apply scaler một lần duy nhất. Gọi trước predict() hoặc predict_proba()."""
    if self.scaler:
        return self.scaler.transform(features)
    return features

def predict(self, features: np.ndarray) -> np.ndarray:
    if not self.is_loaded:
        raise ValueError("Model not loaded")
    scaled = self._apply_scaler(features)   # ← scale ở đây
    if self.model_type == 'tensorflow':
        predictions = self.model.predict(scaled, verbose=0)
        return np.argmax(predictions, axis=1)
    return self.model.predict(scaled)

def predict_proba(self, features: np.ndarray) -> np.ndarray:
    if not self.is_loaded:
        raise ValueError("Model not loaded")
    scaled = self._apply_scaler(features)   # ← scale ở đây (cùng input chưa scale)
    if self.model_type == 'tensorflow':
        return self.model.predict(scaled, verbose=0)
    if hasattr(self.model, 'predict_proba'):
        return self.model.predict_proba(scaled)
    predictions = self.model.predict(scaled)
    proba = np.zeros((len(predictions), 2))
    proba[:, 1] = predictions
    proba[:, 0] = 1 - predictions
    return proba
```

**Quan trọng:** Trong `Predictor.predict_flow()`, features được pass vào `model_loader.predict()` và `model_loader.predict_proba()` **riêng lẻ** — mỗi lần là một array chưa scale. Sau fix, mỗi call sẽ scale một lần → đúng.

**Verify:**
```python
import numpy as np
from backend.detection_engine.model_loader import get_model_loader

loader = get_model_loader()
loader.load_from_directory("ensemble")

# Test với features giả
features = np.array([[1.5, 100, 50, 10000, 5000, 100, 50, 5000,
                       2, 1, 0, 5, 50, 1, 0.01, 30, 20, 3000, 2000, 100]])

pred1 = loader.predict(features.copy())
pred2 = loader.predict(features.copy())
assert np.array_equal(pred1, pred2), "Same input should give same output"

proba1 = loader.predict_proba(features.copy())
proba2 = loader.predict_proba(features.copy())
assert np.allclose(proba1, proba2), "Same input should give same probabilities"
print("✅ M4 fix verified — scaler applied exactly once per call")
```

---

#### M5 — `Dockerfile` copies `.env.example` as `.env`

> 🟡 **Tại sao nguy hiểm?** Dòng `COPY .env.example .env` bake credentials mẫu vào Docker image layer. Bất kỳ ai pull image đều có thể extract layer và đọc credentials.

**File:** `Dockerfile`

```dockerfile
# TRƯỚC KHI SỬA
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY .env.example .env    # ← XÓA DÒNG NÀY
RUN mkdir -p models logs data
```

```dockerfile
# SAU KHI SỬA
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
# .env.example đã bị xóa — config được inject qua docker-compose environment:
RUN mkdir -p models logs data
```

**Verify:**
```bash
docker build -t ids-backend-test .
docker run --rm ids-backend-test cat /app/.env
# Phải thấy: cat: /app/.env: No such file or directory
# KHÔNG thấy: nội dung của .env.example
```

---

#### M6 — No `__init__.py` in `monitoring/` and `cache/`

> 🟡 **Tại sao nguy hiểm?** Python 3 hỗ trợ namespace packages (không cần `__init__.py`), nhưng một số tools (pytest, mypy, coverage) có thể không discover modules đúng cách nếu thiếu file này.

**Fix — tạo 2 file rỗng:**

```bash
# Windows PowerShell
New-Item -ItemType File "backend\monitoring\__init__.py"
New-Item -ItemType File "backend\cache\__init__.py"
```

```bash
# Linux/Mac
touch backend/monitoring/__init__.py
touch backend/cache/__init__.py
```

**Verify:**
```bash
python -c "from backend.monitoring.metrics import metrics_endpoint; print('✅ monitoring import OK')"
python -c "from backend.cache.redis_cache import get_cache; print('✅ cache import OK')"
```

---

### 4.4 Low-Risk / Code Quality Issues

> 🟢 **Những vấn đề này không gây crash** nhưng nên fix để code sạch hơn và tránh deprecation warnings trong Python/library versions mới.

| ID | Vấn đề | File | Fix cụ thể |
|---|---|---|---|
| L1 | `datetime.utcnow()` deprecated Python 3.12 | Tất cả files | Thay bằng `datetime.now(timezone.utc)` — cần `from datetime import timezone` |
| L2 | `declarative_base()` deprecated SQLAlchemy 2.0 | `database/models.py` | Thay bằng `from sqlalchemy.orm import DeclarativeBase; class Base(DeclarativeBase): pass` |
| L3 | `python-multipart` xuất hiện 2 lần trong requirements | `requirements.txt` | Xóa dòng `python-multipart==0.19.0` (giữ `==0.0.6`) |
| L4 | `legacy_routes.py` — tên file gây nhầm lẫn | `api/legacy_routes.py` | Rename thành `api/routes/alerts.py` khi có thời gian refactor |
| L5 | `IDSModel` trong legacy routes không dùng trong pipeline | `api/legacy_routes.py` | Unify: dùng `ModelLoader` + `Predictor` cho cả hai paths |
| L6 | Thiếu `__init__.py` trong `monitoring/` | `backend/monitoring/` | `touch backend/monitoring/__init__.py` |
| L7 | `tensorflow==2.15.0` nặng (~500MB) cho graduation project | `requirements.txt` | Wrap import trong try/except, chỉ load khi cần |
| L8 | `locust` trong main requirements | `requirements.txt` | Chuyển sang `requirements-dev.txt` |

**Fix L1 — datetime.utcnow() (áp dụng cho tất cả files):**
```python
# TRƯỚC
from datetime import datetime
timestamp = datetime.utcnow()

# SAU
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc)
```

**Fix L2 — declarative_base() (database/models.py):**
```python
# TRƯỚC
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

# SAU (SQLAlchemy 2.0+)
from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase):
    pass
```

**Fix L7 — TensorFlow optional import (detection_engine/model_loader.py):**
```python
# TRƯỚC
import tensorflow as tf  # crash nếu TF không install

# SAU — lazy import chỉ khi cần
def _load_tensorflow_model(self, model_path):
    try:
        import tensorflow as tf
        return tf.keras.models.load_model(str(model_path))
    except ImportError:
        raise ImportError(
            "TensorFlow not installed. Install with: pip install tensorflow==2.15.0"
        )
```

---

## 5. Module-by-Module Analysis

> 💡 **Cách đọc section này:** Mỗi module được phân tích theo cấu trúc: Trách nhiệm → Điểm tốt → Vấn đề → Fix cụ thể. Đọc theo thứ tự từ trên xuống vì các module phụ thuộc nhau theo đúng thứ tự đó.
>
> **Thứ tự đọc code khi debug:** `main.py` → `config.py` → `pipeline/coordinator.py` → `capture_engine/` → `flow_engine/` → `feature_engine/` → `detection_engine/` → `alert_engine/` → `api/websocket.py`

### 5.1 `backend/main.py` — Application Entry Point

> **Vai trò:** File này là "cổng vào" của toàn bộ ứng dụng. Nó không chứa business logic — chỉ kết nối các thành phần lại với nhau. Khi debug startup issues, đây là file đầu tiên cần đọc.

**Responsibility:** Bootstrap FastAPI app, configure middleware, register routers, manage lifespan.

**What it does well:**
- Uses `@asynccontextmanager` lifespan (correct modern FastAPI pattern)
- Validates CORS origins at startup, exits if empty in production
- Validates settings at startup, exits on insecure production config
- Starts the broadcast bridge consumer as a lifespan task

**Problems:**

1. **Settings instantiated at module level before lifespan:**
   ```python
   settings = get_settings()  # ← runs at import time
   app = FastAPI(..., max_request_size=settings.max_request_size)
   ```
   If `.env` is missing or malformed, the import fails with an unhandled exception rather than a clean startup error.

2. **`api_reload: True` default** — see H4 above.

3. **WebSocket endpoint is public** — no authentication on `/ws`. Any client can connect and receive all security alerts. This is intentional for the graduation demo but must be documented.

4. **`if __name__ == "__main__"` uses `reload=True`** — same issue as H4.

**Recommended changes:**
```python
# main.py — wrap settings in try/except at module level
try:
    settings = get_settings()
except Exception as e:
    import sys
    print(f"FATAL: Configuration error: {e}", file=sys.stderr)
    sys.exit(1)
```

---

### 5.2 `backend/config.py` — Settings Management

> **Vai trò:** Tất cả configuration của hệ thống đều đi qua file này. Không bao giờ hardcode giá trị config trong code — luôn dùng `settings.xxx`. File này cũng là "security gate" đầu tiên: nếu production config không an toàn, app từ chối khởi động.

**Responsibility:** Load and validate all environment variables via Pydantic Settings.

**What it does well:**
- `model_validator` blocks startup with insecure production secrets
- `lru_cache` ensures single Settings instance
- URI override pattern for MongoDB and Redis (`mongo_uri`, `redis_url`)
- Warns on default secrets in development

**Problems:**

1. **`cors_origins` is a `@property`** — Pydantic Settings doesn't serialize properties. If you ever need to serialize settings to JSON (e.g. for a `/config` debug endpoint), `cors_origins` won't appear.

2. **`api_reload: bool = True`** — should default to `False`.

3. **`mongo_db` and `mongodb_db` are redundant** — two fields for the same thing. Pick one.

4. **No validation on `prediction_mode`** — any string is accepted at the settings level; validation only happens in `PipelineCoordinator.__init__()`.

---

### 5.3 `backend/capture_engine/packet_sniffer.py` — Packet Capture

> **Vai trò:** Đây là điểm tiếp xúc với network hardware. File này chạy Scapy trong một daemon thread riêng biệt — hoàn toàn tách biệt với FastAPI event loop. Mọi packet từ network interface đều đi qua đây trước tiên.
>
> **Khi debug:** Nếu pipeline không nhận được packets, kiểm tra file này trước. Các lỗi thường gặp: Npcap chưa cài (Windows), thiếu NET_RAW capability (Docker), tên interface sai.

**Responsibility:** Wrap Scapy's `sniff()` in a daemon thread, extract packet metadata, invoke callback.

**What it does well:**
- Daemon thread (won't block process exit)
- BPF filter support
- Dry-run mode for testing without real traffic
- Windows Npcap detection with helpful error messages
- Queue-based buffering (maxsize=10,000)

**Problems:**

1. **Singleton is never reset between pipeline restarts:**
   ```python
   _sniffer_instance: Optional[PacketSniffer] = None
   
   def get_sniffer(...) -> PacketSniffer:
       if _sniffer_instance is None:
           _sniffer_instance = PacketSniffer(...)
       return _sniffer_instance  # ← returns old instance even after stop()
   ```
   After `stop()` + `start()`, `get_sniffer()` returns the stopped instance. The `PipelineCoordinator` calls `get_sniffer()` in `initialize()`, so a second pipeline start will reuse a dead sniffer.

   **Fix:** Reset `_sniffer_instance = None` in `stop()`, or create a new `PacketSniffer` in `PipelineCoordinator.initialize()` without using the singleton.

2. **`_packet_handler` calls callback synchronously** — the callback is `PipelineCoordinator.packet_callback()` which does ML inference. If inference is slow, it blocks the packet handler, causing queue buildup.

3. **`datetime.utcnow()` in `_extract_packet_info()`** — deprecated in Python 3.12.

4. **Queue is also filled AND callback is called** — double processing path. The queue is never consumed by the coordinator (coordinator uses callback only). The queue fills up silently.

   **Fix:** Either use the queue OR the callback, not both. The coordinator uses callback; the queue is dead code.

---

### 5.4 `backend/flow_engine/flow_builder.py` — Flow Aggregation

> **Vai trò:** Gom các packets rời rạc thành "flows" có ý nghĩa. Một flow là tập hợp tất cả packets giữa cùng một cặp (src_ip:port ↔ dst_ip:port:protocol). Đây là bước chuyển đổi từ "packet-level" sang "flow-level" — cần thiết vì ML model được train trên flow features, không phải packet features.
>
> **Ví dụ:** 1000 packets TCP từ 192.168.1.5:54321 đến 10.0.0.1:80 → 1 Flow object với packet_count=1000, byte_count=X, syn_count=1, ack_count=998, v.v.

**Responsibility:** Maintain a dict of active flows keyed by 5-tuple, aggregate packet statistics per flow.

**What it does well:**
- Clean `Flow` class with all relevant statistics
- Three-tier expiry: inactivity, max lifetime, post-prediction retention
- `should_run_inference()` with `once` and `window` modes
- `mark_inference_complete()` for inference gating

**Problems:**

1. **`self.flows` dict is not thread-safe** — see H6 above.

2. **`inter_arrival_times` list grows unbounded** — see M1 above.

3. **`cleanup_expired_flows()` iterates and deletes in two passes** — this is correct (collect keys first, then delete), but the iteration itself is not protected by a lock.

4. **`get_flow_builder()` singleton mutates existing instance:**
   ```python
   else:
       _flow_builder_instance.flow_expire_sec = flow_expire_sec
   ```
   If the pipeline is restarted with different parameters, the existing flows in memory are now subject to new expiry rules. This is probably fine for a graduation project but should be documented.

---

### 5.5 `backend/feature_engine/feature_extractor.py` — Feature Extraction

> **Vai trò:** Chuyển đổi một Flow object thành vector 20 số thực để đưa vào ML model. Đây là bước "feature engineering" — quyết định model nhìn thấy gì. Thứ tự của 20 features phải khớp chính xác với thứ tự khi training (được enforce bởi `models/features.json`).
>
> **Khi debug inference sai:** Kiểm tra feature values có hợp lý không. Ví dụ: `packet_rate = 0` khi `flow_duration = 0` (flow quá ngắn) là bình thường.

**Responsibility:** Convert a `Flow` object into a 20-feature dict for ML inference.

**What it does well:**
- Clean, stateless transformation
- All features derived from `flow.get_stats()` (no direct Flow field access)
- Fills missing features with 0.0

**Problems:**

1. **`avg_packet_size` and `packet_length_mean` are identical:**
   ```python
   features['avg_packet_size'] = total_bytes / total_packets
   features['packet_length_mean'] = total_bytes / total_packets
   ```
   Both compute `total_bytes / total_packets`. This wastes a feature slot and may confuse the model.

2. **No variance/std features** — real IDS feature sets (CIC-IDS2017) include `packet_length_std`, `flow_iat_std`, etc. The current 20 features are a simplified subset.

3. **`normalize_features()` is defined but never called in the pipeline** — normalization is handled by the scaler inside `ModelLoader`. This method is dead code.

---

### 5.6 `backend/detection_engine/predictor.py` — ML Inference

> **Vai trò:** Nhận feature dict, validate, chạy model, trả về kết quả phân loại. File này là "brain" của IDS — nơi quyết định một flow có phải tấn công không. Nó cũng enforce feature contract để đảm bảo training và inference dùng cùng feature order.
>
> **Khi debug predictions sai:** Kiểm tra `features.json` có khớp với `feature_extractor.py` không. Chạy `python backend/scripts/validate_features.py`.

**Responsibility:** Validate features, run model inference, determine severity.

**What it does well:**
- `FeatureContractError` for feature mismatch detection
- `features.json` contract validation at startup
- NaN/Inf replacement before inference
- `is_attack()` confidence gating

**Problems:**

1. **`predict_flow()` calls `extract_features()` again** — the coordinator already called `extract_features()` before calling `predict_flow()`. The predictor calls it a second time internally:
   ```python
   def predict_flow(self, flow: Flow) -> Dict:
       features = self.feature_extractor.extract_features(flow)  # ← second call
   ```
   This means features are extracted twice per inference. The coordinator's `features` variable (used for DB save) and the predictor's internal `features` are separate extractions — they should be identical but this is wasteful and fragile.

   **Fix:** Accept `features: dict` as a parameter to `predict_flow()` instead of re-extracting.

2. **`confidence_threshold` is hardcoded at 0.75** — not configurable from settings.

3. **`_determine_severity()` thresholds are hardcoded** — should use `settings.alert_threshold_*` values.

---

### 5.7 `backend/detection_engine/model_loader.py` — Model Loading

> **Vai trò:** Load và quản lý ML model artifacts từ disk. Hỗ trợ 3 loại model: sklearn (`.pkl`), XGBoost (`.pkl`), TensorFlow (`.h5`). Cũng load scaler và label encoder đi kèm.
>
> **Files cần có trong `models/`:** `ensemble.pkl`, `ensemble_scaler.pkl`, `ensemble_encoder.pkl`, `features.json`. Thiếu bất kỳ file nào → pipeline không start được.

**Responsibility:** Load `.pkl` / `.joblib` / `.h5` model artifacts, apply scaler, run inference.

**What it does well:**
- Supports sklearn, XGBoost, and TensorFlow models
- Optional scaler and label encoder loading
- `pool_pre_ping=True` equivalent: `is_loaded` flag

**Problems:**

1. **Scaler applied inside `predict()` and `predict_proba()` separately** — the scaler transform is applied twice if both methods are called for the same input (which `predict_flow()` does: calls `predict()` then `predict_proba()`). The second call re-transforms already-transformed features.

   **Fix:** Apply scaler once before calling both methods, or cache the scaled array.

2. **`get_model_loader()` singleton ignores `model_dir` parameter after first call** — if called with a different `model_dir`, it silently returns the old instance.

3. **No model validation after loading** — no check that the loaded model has the expected number of input features.

---

### 5.8 `backend/alert_engine/alert_manager.py` — Alert Generation

> **Vai trò:** Đây là "bộ lọc thông minh" cuối cùng trước khi một sự kiện trở thành alert. Nó quyết định: có nên sinh alert không? Severity là gì? Gửi đi đâu? File này chứa nhiều bugs nhất trong dự án (C1, C2, C5, M2).
>
> **Khi debug:** Nếu alerts không xuất hiện dù pipeline đang chạy, kiểm tra: (1) confidence có >= 0.75 không? (2) IP có trong whitelist không? (3) IP có đang trong cooldown không? Dùng `GET /api/stats/alert-engine` để xem stats.

**Responsibility:** Generate, correlate, gate, and dispatch alerts.

**What it does well:**
- Redis-backed cooldown với in-memory fallback — resilient khi Redis down
- Sliding-window correlation để escalate severity khi cùng IP tấn công nhiều lần
- Whitelist support — bỏ qua IPs tin cậy
- Thread-safe broadcast qua `AlertBroadcastBridge`

**Problems:**

1. **NameError bug trong `get_alert_history()`** — xem C5 ở trên. Fix ngay, 1 dòng.

2. **Synchronous DB writes trên sniffer thread** — xem C1. Fix quan trọng nhất.

3. **Email dispatch từ sniffer thread** — xem C2. Fix quan trọng thứ hai.

4. **`attack_patterns` dict tăng không giới hạn** — xem M2.

5. **`alert_history` (in-memory) và Redis cooldown đều được maintain** — redundant state. Khi Redis available, in-memory dict không bao giờ được dùng để check cooldown nhưng vẫn được update. Lãng phí memory.

   **Fix:** Khi Redis available, bỏ qua việc update `self.alert_history`:
   ```python
   def _update_alert_history(self, ip_address: str):
       cache = get_cache()
       if cache.is_connected():
           cache.set_alert_cooldown(ip_address, self.alert_cooldown)
           # Không cần update in-memory khi Redis available
           return
       # Chỉ update in-memory khi Redis không available (fallback)
       self.alert_history[ip_address] = datetime.utcnow()
   ```

---

### 5.9 `backend/api/websocket.py` — WebSocket & Broadcast Bridge

> **Vai trò:** File này giải quyết vấn đề khó nhất trong dự án: làm thế nào để sniffer thread (sync) gửi alerts đến WebSocket clients (async) một cách an toàn. Giải pháp là `AlertBroadcastBridge` — một queue thread-safe làm cầu nối giữa hai execution contexts.
>
> **Khi debug WebSocket không nhận alerts:** Kiểm tra `GET /api/stats/alert-engine` → xem `bridge.enqueued_total` và `bridge.broadcast_total`. Nếu enqueued tăng nhưng broadcast không tăng → consumer loop bị stuck.

**Responsibility:** Manage WebSocket connections and provide thread-safe alert broadcasting.

**What it does well:**
- `AlertBroadcastBridge` tách biệt đúng đắn thread-safe enqueue khỏi async broadcast
- `asyncio.to_thread()` cho blocking queue.get — đúng pattern
- Shutdown sentinel để consumer exit sạch
- Drain remaining queue khi shutdown
- Stats tracking (enqueued, broadcast, dropped)

**Problems:**

1. **`asyncio.to_thread()` spawn thread mỗi 0.25 giây** — mỗi poll cycle tạo một thread mới để gọi `queue.Queue.get(timeout=0.25)`. Dưới high alert volume, tạo nhiều short-lived threads.

   **Fix:** Dùng `asyncio.Queue` thay `queue.Queue`. Xem Section 7 để biết implementation đầy đủ.

2. **Không có authentication trên `/ws`** — bất kỳ client nào cũng nhận được tất cả security alerts. Chấp nhận được cho graduation demo, cần document rõ.

3. **`ConnectionManager.active_connections` là plain list** — concurrent connect/disconnect có thể gây list mutation issues. Trong thực tế FastAPI WebSocket handling là single-threaded trên event loop nên ít xảy ra, nhưng nên dùng `set` thay `list` để an toàn hơn.

---

### 5.10 `backend/pipeline/coordinator.py` — Pipeline Orchestration

> **Vai trò:** File này là "nhạc trưởng" — nó không làm gì trực tiếp mà chỉ kết nối tất cả engines lại và điều phối luồng xử lý. Đây là file duy nhất biết về tất cả các components khác.
>
> **Khi debug pipeline không hoạt động:** Kiểm tra `GET /api/sniffer/status` → xem `processed_packets`, `inference_runs`, `skipped_below_min_packets`. Nếu `processed_packets` tăng nhưng `inference_runs = 0` → min_packets threshold quá cao hoặc flows quá ngắn.

**Responsibility:** Wire all pipeline components together, manage pipeline lifecycle.

**What it does well:**
- Clean `initialize()` / `start()` / `stop()` lifecycle
- Configurable inference gating (min_packets, prediction_mode, interval)
- Periodic cleanup mỗi 50 inference runs và mỗi 500 packets
- Comprehensive stats qua `get_stats()`

**Problems:**

1. **`packet_callback()` chạy trên sniffer thread** — tất cả vấn đề C1 và C2 bắt nguồn từ đây. DB writes và email dispatch đều xảy ra trong callback này.

2. **`coordinator.start()` là async method loop `await asyncio.sleep(1)`** — đây là keep-alive loop, không phải actual work. Work thực sự xảy ra trong `packet_callback()` trên sniffer thread. Async loop chỉ tồn tại để giữ asyncio task alive. Đúng nhưng confusing — nên có comment giải thích.

3. **`get_coordinator()` singleton mutation** — xem C3.

4. **`_save_flow_to_db()` tạo `SessionLocal()` mới mỗi lần gọi** — mỗi attack detected mở và đóng một DB connection. Dưới high attack rate, tạo connection pool pressure.

   **Fix ngắn hạn:** Reuse session trong cùng một `packet_callback()` call:
   ```python
   def _save_flow_and_alert_to_db(self, flow, features, alert):
       """Lưu flow, features, và alert trong một transaction duy nhất."""
       try:
           db = SessionLocal()
           try:
               traffic_flow = TrafficFlowRepository.create_flow(db, flow.get_stats())
               FlowFeatureRepository.create_feature(db, features, traffic_flow.id)
               AttackAlertRepository.create_alert(db, alert, traffic_flow.id)
               AttackHistoryRepository.update_or_create_history(
                   db, alert['src_ip'], alert['attack_type'], alert['severity']
               )
               return traffic_flow.id
           finally:
               db.close()
       except Exception as exc:
           logger.error("Error saving to database: %s", exc)
           return None
   ```

---

### 5.11 `backend/database/` — Persistence Layer

> **Vai trò:** Tất cả tương tác với PostgreSQL, MongoDB, và Redis đều đi qua thư mục này. Repository pattern đảm bảo business logic không biết gì về SQL — chỉ gọi `TrafficFlowRepository.create_flow(db, data)`.
>
> **Files quan trọng:**
> - `models.py` — định nghĩa schema (thay đổi ở đây cần migration)
> - `connection.py` — connection pools và clients
> - `repository.py` — tất cả CRUD operations
> - `mongo_logger.py` — fire-and-forget MongoDB logging

**Responsibility:** PostgreSQL ORM models, repository pattern, MongoDB logging, connection management.

**What it does well:**
- Repository pattern tách biệt DB logic khỏi business logic
- `pool_pre_ping=True` để check connection health trước mỗi query
- `QueuePool` với defaults hợp lý (pool_size=10, max_overflow=20)
- MongoDB URI override cho Docker deployment

**Problems:**

1. **Không có Alembic migrations** — xem H1. Bất kỳ schema change nào đều cần `DROP TABLE` thủ công.

2. **`flow_key` UNIQUE constraint phá vỡ window mode** — xem C4. Fix:
   ```python
   # repository.py — thay create_flow() bằng upsert
   @staticmethod
   def create_or_update_flow(db: Session, flow_data: dict) -> TrafficFlow:
       """INSERT ... ON CONFLICT (flow_key) DO UPDATE"""
       from sqlalchemy.dialects.postgresql import insert
       stmt = insert(TrafficFlow).values(**flow_data)
       stmt = stmt.on_conflict_do_update(
           index_elements=['flow_key'],
           set_={
               'packet_count': stmt.excluded.packet_count,
               'byte_count': stmt.excluded.byte_count,
               'last_seen': stmt.excluded.last_seen,
           }
       )
       result = db.execute(stmt)
       db.commit()
       return db.query(TrafficFlow).filter(
           TrafficFlow.flow_key == flow_data['flow_key']
       ).first()
   ```

3. **`declarative_base()` deprecated** — xem L2.

4. **Hai patterns lấy DB session** — `get_db()` generator (FastAPI DI) và `SessionLocal()` trực tiếp (pipeline). Nên thống nhất: pipeline dùng `SessionLocal()` trực tiếp là đúng vì nó không chạy trong request context.

5. **`close_connections()` không được gọi trong lifespan** — xem H5.

---

### 5.12 `backend/api/middleware/rate_limit.py` — Rate Limiting

> **Vai trò:** Bảo vệ các endpoints nhạy cảm khỏi bị spam. Dùng sliding window algorithm — chính xác hơn fixed window (không có "burst at boundary" problem).
>
> **Khi test:** Dùng `reset_ip("your-ip")` hoặc `reset_all()` để clear state giữa các test cases.

**Responsibility:** Sliding-window per-IP rate limiting for sensitive endpoints.

**What it does well:**
- Correct sliding window implementation — không có boundary burst problem
- `threading.Lock` cho thread safety
- `Retry-After` header trong 429 response — clients biết khi nào retry
- Test helpers (`reset_all()`, `reset_ip()`)

**Problems:**

1. **`_windows` dict tăng không giới hạn** — xem M3. Fix: thêm `_cleanup_stale_windows()`.

2. **Rate limits hardcoded** — `/api/sniffer/` giới hạn 10 req/60s. Quá restrictive cho automated testing. Nên đọc từ settings:
   ```python
   # config.py — thêm
   rate_limit_sniffer: int = 10   # req per 60s
   rate_limit_whitelist: int = 30
   rate_limit_xai: int = 60

   # rate_limit.py — đọc từ settings
   from backend.config import get_settings
   _settings = get_settings()
   _ROUTE_LIMITS = [
       ("/api/sniffer/",   _settings.rate_limit_sniffer,   60),
       ("/api/whitelist/", _settings.rate_limit_whitelist, 60),
       ("/api/xai/",       _settings.rate_limit_xai,       60),
   ]
   ```

3. **`X-Forwarded-For` trust không có validation** — bất kỳ client nào cũng có thể spoof IP bằng cách set header này, bypass rate limiting. Xem S3 trong Section 11 để biết fix.

---

## 5.13 Tóm tắt: Dependency Map giữa các modules

> 💡 **Đọc diagram này khi cần hiểu "nếu tôi sửa file X, file nào khác bị ảnh hưởng?"**

```
main.py
  ├── config.py                    (import lúc startup)
  ├── database/connection.py       (init_db trong lifespan)
  ├── api/websocket.py             (bridge trong lifespan)
  ├── alert_engine/alert_manager.py (set_broadcast_bridge trong lifespan)
  └── api/routes/sniffer.py        (pipeline_coordinator trong lifespan shutdown)

api/routes/sniffer.py
  └── pipeline/coordinator.py
        ├── capture_engine/packet_sniffer.py
        ├── flow_engine/flow_builder.py
        ├── feature_engine/feature_extractor.py
        ├── detection_engine/model_loader.py
        ├── detection_engine/predictor.py
        │     ├── detection_engine/model_loader.py
        │     └── feature_engine/feature_extractor.py  ← DUPLICATE CALL (bug)
        ├── alert_engine/alert_manager.py
        │     ├── database/connection.py  (SessionLocal)
        │     ├── database/repository.py
        │     ├── notifications/email.py
        │     └── cache/redis_cache.py
        ├── database/connection.py  (SessionLocal)
        ├── database/repository.py
        └── database/mongo_logger.py

api/websocket.py
  └── (standalone — không import business logic)

api/legacy_routes.py
  ├── database/connection.py  (get_db dependency)
  ├── database/models.py
  └── alert_engine/alert_manager.py
```

---

## 6. Thread Ownership Model

> 💡 **Đây là section quan trọng nhất để debug.** Hầu hết bugs khó trong dự án này đều liên quan đến việc code chạy trên sai thread. Trước khi debug bất kỳ vấn đề nào, hãy tự hỏi: "Code này đang chạy trên thread nào?"
>
> **Quy tắc vàng:** Sniffer thread và event loop KHÔNG được gọi trực tiếp vào nhau. Chúng chỉ giao tiếp qua `queue.Queue` (thread-safe).

Understanding which code runs on which thread is the most important thing for debugging this system.

```mermaid
graph LR
    subgraph "Thread: sniffer-thread (daemon)"
        ST1[scapy sniff()]
        ST2[_packet_handler()]
        ST3[packet_callback()]
        ST4[FlowBuilder.add_packet()]
        ST5[FeatureExtractor.extract_features()]
        ST6[Predictor.predict_flow()]
        ST7[AlertManager.generate_alert()]
        ST8[AlertBroadcastBridge.enqueue_alert()]
        ST9[SessionLocal DB writes ← PROBLEM]
    end

    subgraph "Thread: asyncio event loop (main)"
        EL1[FastAPI request handlers]
        EL2[AlertBroadcastBridge._consume_loop()]
        EL3[ConnectionManager.broadcast()]
        EL4[email_service.send_alert_email()]
        EL5[asyncio.to_thread() workers]
    end

    subgraph "Thread: uvicorn worker threads"
        UV1[HTTP request handling]
    end

    ST1 --> ST2 --> ST3 --> ST4 --> ST5 --> ST6 --> ST7 --> ST8
    ST7 --> ST9
    ST8 -->|queue.put_nowait| EL2
    EL2 -->|asyncio.to_thread| EL5
    EL5 -->|queue.get| EL2
    EL2 --> EL3 --> EL4
```

### Rules for Safe Cross-Thread Communication

| From | To | Safe Method |
|---|---|---|
| Sniffer thread → Event loop | `AlertBroadcastBridge.enqueue_alert()` (queue.put_nowait) |
| Sniffer thread → Event loop | `loop.call_soon_threadsafe(coro_or_callback)` |
| Event loop → Blocking I/O | `await asyncio.to_thread(blocking_func)` |
| Event loop → Sync code | Direct call (runs on event loop, blocks it) |

### What MUST NOT happen

- **Never call `await` from the sniffer thread** — there is no event loop there
- **Never call `asyncio.get_event_loop()` from the sniffer thread** — deprecated/broken in Python 3.10+
- **Never call `SessionLocal()` from the sniffer thread** — blocks packet processing
- **Never mutate `FlowBuilder.flows` from both threads without a lock**

---

## 7. WebSocket Architecture

> 💡 **Tại sao section này quan trọng?** WebSocket là cách duy nhất để frontend nhận alerts real-time. Nếu WebSocket không hoạt động, dashboard sẽ không hiển thị alerts mới cho đến khi user refresh page và gọi `GET /api/alerts/`.
>
> **Vấn đề cốt lõi:** Sniffer thread (sync) cần gửi data đến WebSocket clients (async). Hai thế giới này không thể gọi trực tiếp vào nhau. `AlertBroadcastBridge` là cầu nối giải quyết vấn đề này.

### Current Design

```
Sniffer Thread                    Event Loop Thread
─────────────────                 ─────────────────────────────────
AlertManager.generate_alert()
  └─ bridge.enqueue_alert(alert)  ←── queue.Queue (thread-safe)
                                       │
                                  _consume_loop()
                                    asyncio.to_thread(
                                      blocking_get, 0.25s
                                    )
                                       │
                                  _dispatch(message)
                                    ConnectionManager.broadcast()
                                       │
                                  websocket.send_text(json)
                                       │
                                  Frontend Dashboard
```

### Why `asyncio.to_thread()` is used

The `queue.Queue.get(timeout=0.25)` call is blocking. You cannot call it directly in an async function without blocking the event loop. `asyncio.to_thread()` runs it in a thread pool executor, freeing the event loop while waiting.

### Better Alternative: `asyncio.Queue`

The current design spawns a thread every 0.25 seconds. A cleaner approach:

```python
# In AlertBroadcastBridge
self._async_queue: asyncio.Queue = asyncio.Queue(maxsize=10_000)

# Sniffer thread enqueues via:
loop.call_soon_threadsafe(self._async_queue.put_nowait, message)

# Consumer:
async def _consume_loop(self):
    while self._running:
        message = await self._async_queue.get()
        await self._dispatch(message)
```

This eliminates the thread-per-poll overhead. The tradeoff: you need to store a reference to the event loop at startup (`self._loop = asyncio.get_event_loop()`).

### WebSocket Authentication Gap

The `/ws` endpoint has no authentication:

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)  # ← no auth check
```

For a graduation demo this is acceptable. For production, add a token query parameter:

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    if not verify_token(token):
        await websocket.close(code=4001)
        return
    await manager.connect(websocket)
```

---

## 8. Alert Pipeline

> 💡 **Section này trả lời câu hỏi:** "Từ lúc một gói tin đến network interface cho đến khi alert xuất hiện trên dashboard — chuyện gì xảy ra ở giữa?" Đọc diagram state machine bên dưới để hiểu tất cả các "cổng" mà một packet phải đi qua trước khi trở thành alert.
>
> **Quan trọng cho thesis defense:** Giải thích được alert pipeline = giải thích được toàn bộ hệ thống. Đây là phần hội đồng sẽ hỏi nhiều nhất.

### Full Alert Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PacketArrives
    PacketArrives --> FlowUpdated: add_packet()
    FlowUpdated --> InferenceSkipped: below min_packets\nor already processed
    FlowUpdated --> FeaturesExtracted: should_run_inference() = True
    FeaturesExtracted --> PredictionMade: predict_flow()
    PredictionMade --> NormalTraffic: attack_type == "Normal"
    PredictionMade --> AttackDetected: attack_type != "Normal"\nAND confidence >= 0.75
    AttackDetected --> Whitelisted: src_ip in whitelist
    AttackDetected --> Cooldown: Redis TTL exists for src_ip
    AttackDetected --> Correlated: apply_correlation()
    Correlated --> AlertGenerated: severity adjusted
    AlertGenerated --> DBSaved: _save_alert_to_db()
    AlertGenerated --> Enqueued: bridge.enqueue_alert()
    AlertGenerated --> EmailQueued: dispatch_alert_email()
    Enqueued --> Broadcast: _consume_loop() → broadcast()
    Broadcast --> WebSocketClients: send_text(json)
    NormalTraffic --> [*]
    InferenceSkipped --> [*]
    Whitelisted --> [*]
    Cooldown --> [*]
```

### Alert Severity Escalation Logic

```
Base severity from Predictor._determine_severity():
  confidence >= 0.9  → critical
  confidence >= 0.8  → high
  confidence >= 0.75 → medium
  else               → low

Correlation escalation in AlertManager._apply_correlation():
  recent_attacks >= 5 AND severity in [low, medium] → high
  recent_attacks >= 5 AND severity == high           → critical
  attack_type in [PortScan, Port Sweep] AND recent >= 3 → critical
  attack_type == DDoS AND recent >= 2                → critical
```

### Alert Cooldown Strategy

```
Per-IP cooldown (default: 30 seconds):
  1. Check Redis: EXISTS alert_cooldown:{ip}
  2. If Redis unavailable: check in-memory alert_history dict
  3. If in cooldown: suppress alert (return None)
  4. If not in cooldown: set Redis key with TTL, update in-memory dict
```

The dual-layer cooldown (Redis + in-memory) provides resilience when Redis is down. However, if Redis restarts, the in-memory state is the only source of truth until Redis reconnects.

---

## 9. Persistence Pipeline

> 💡 **Section này trả lời câu hỏi:** "Data được lưu ở đâu, khi nào, và bởi ai?" Quan trọng: chỉ traffic bị phát hiện là tấn công mới được lưu. Traffic bình thường KHÔNG được persist — đây là design decision có chủ đích để tránh đầy database.

### What Gets Saved Where

| Data | Storage | When | Who |
|---|---|---|---|
| Traffic flows | PostgreSQL `traffic_flows` | On attack detection | `PipelineCoordinator._save_flow_to_db()` |
| Flow features | PostgreSQL `flow_features` | On attack detection | `PipelineCoordinator._save_flow_to_db()` |
| Attack alerts | PostgreSQL `attack_alerts` | On alert generation | `AlertManager._save_alert_to_db()` |
| Attack history | PostgreSQL `attack_history` | On alert generation | `AlertManager._update_attack_history_db()` |
| Flow summaries | MongoDB `flow_logs` | On attack detection | `mongo_logger.log_flow_summary()` |
| Alert cooldowns | Redis `alert_cooldown:{ip}` | On alert generation | `AlertManager._update_alert_history()` |

### Normal Traffic

Normal traffic (non-attack flows) is **never persisted**. Only flows that trigger an attack prediction are saved to PostgreSQL. This is a deliberate design choice to avoid filling the database with benign traffic.

### Persistence Dependency Graph

```
Attack detected
    │
    ├─► _save_flow_to_db()
    │       ├─► TrafficFlowRepository.create_flow()  → PostgreSQL
    │       └─► FlowFeatureRepository.create_feature() → PostgreSQL
    │
    ├─► log_flow_summary()  → MongoDB (non-blocking, skips on error)
    │
    └─► generate_alert()
            ├─► AttackAlertRepository.create_alert()  → PostgreSQL
            └─► AttackHistoryRepository.update_or_create_history() → PostgreSQL
```

### Problem: 4 Synchronous DB Writes Per Attack

Every detected attack triggers 4 separate synchronous DB operations on the sniffer thread:
1. `TrafficFlowRepository.create_flow()` — INSERT into `traffic_flows`
2. `FlowFeatureRepository.create_feature()` — INSERT into `flow_features`
3. `AttackAlertRepository.create_alert()` — INSERT into `attack_alerts`
4. `AttackHistoryRepository.update_or_create_history()` — SELECT + INSERT/UPDATE into `attack_history`

Each opens and closes a DB connection. Under a DDoS simulation generating 100 alerts/second, this is 400 DB operations/second on the sniffer thread.

### Recommended Fix: Async DB Write Queue

```python
# In lifespan startup:
db_write_queue: asyncio.Queue = asyncio.Queue(maxsize=50_000)
asyncio.create_task(_db_writer_loop(db_write_queue))

# In packet_callback (sniffer thread):
# Instead of direct DB write, enqueue a write job:
loop.call_soon_threadsafe(
    db_write_queue.put_nowait,
    {"type": "flow_alert", "flow": flow.get_stats(), "features": features, "alert": alert}
)

# Async writer loop (event loop):
async def _db_writer_loop(queue: asyncio.Queue):
    while True:
        job = await queue.get()
        await asyncio.to_thread(_write_to_db, job)
```

This decouples packet processing from DB I/O completely.

---

## 10. Queue & Backpressure Handling

> 💡 **Section này trả lời câu hỏi:** "Chuyện gì xảy ra khi hệ thống bị quá tải?" Ví dụ: DDoS attack sinh 1000 alerts/giây — hệ thống xử lý thế nào? Câu trả lời: alerts bị drop. Section này giải thích tại sao và cách cải thiện.

### Current Queues

| Queue | Type | Max Size | Producer | Consumer |
|---|---|---|---|---|
| `PacketSniffer.packet_queue` | `queue.Queue` | 10,000 | Scapy `_packet_handler` | Nobody (dead code) |
| `AlertBroadcastBridge._thread_queue` | `queue.Queue` | 10,000 | `AlertManager.enqueue_alert()` | `_consume_loop()` via `asyncio.to_thread` |

### Backpressure Behavior

**Packet queue (dead code):** When full, packets are dropped with a warning log. The coordinator never reads from this queue — it uses the callback instead. This queue is wasted memory.

**Alert broadcast queue:** When full (10,000 alerts queued), new alerts are dropped with a warning. The `dropped_total` counter tracks this. Under normal operation, the consumer processes alerts faster than they arrive, so this queue rarely fills.

### What Happens Under Extreme Load

```
Scenario: DDoS attack generating 1000 alerts/second

1. Sniffer thread: packet_callback() called 1000x/sec
2. Each call: ML inference (~1ms) + DB write (~5ms) = ~6ms/packet
3. At 6ms/packet: sniffer thread can process ~166 packets/sec
4. Remaining 834 packets/sec: dropped (queue full warning)
5. Alert broadcast queue: 1000 alerts/sec enqueued
6. Consumer: broadcasts ~100 alerts/sec (WebSocket I/O bound)
7. Queue fills in ~10 seconds → alerts dropped
```

### Recommended Backpressure Strategy

1. **Remove DB writes from sniffer thread** (see Section 9)
2. **Reduce inference frequency** — use `prediction_mode=once` (default) so each flow is only predicted once
3. **Increase `min_packets`** — higher threshold means fewer flows trigger inference
4. **Add alert deduplication** — if the same src_ip generates 100 alerts in 1 second, only broadcast 1

---

## 11. Security Hardening

> 💡 **Section này dành cho thesis defense.** Hội đồng sẽ hỏi: "Hệ thống có an toàn không?" Bảng dưới đây cho thấy những gì đã làm tốt (✅) và những gì còn thiếu (❌). Quan trọng: hệ thống đã có API key auth, rate limiting, input validation — đây là 3 controls quan trọng nhất cho một graduation project.

### Current Security Controls

| Control | Implementation | Status |
|---|---|---|
| API authentication | X-API-Key header, `secrets.compare_digest` | ✅ Good |
| Production secret validation | `model_validator` blocks startup | ✅ Good |
| CORS | Configurable origins, empty = startup failure | ✅ Good |
| Rate limiting | Sliding window per IP | ✅ Good |
| Input validation | IPv4 regex, interface name regex, port range | ✅ Good |
| SQL injection | SQLAlchemy ORM (parameterized) | ✅ Good |
| WebSocket auth | None | ⚠️ Missing |
| Container privileges | `privileged: true` | ❌ Dangerous |
| Credential management | Hardcoded in docker-compose.yml | ❌ Bad |
| HTTPS | Nginx config referenced but not included | ⚠️ Incomplete |

### Security Issues Detail

#### S1 — `privileged: true` in Docker Compose

This gives the container full access to the host kernel. An attacker who compromises the container can escape to the host.

```yaml
# CURRENT — dangerous
privileged: true
cap_add:
  - NET_RAW
  - NET_ADMIN

# FIXED — minimal capabilities
cap_add:
  - NET_RAW
  - NET_ADMIN
# Remove privileged: true entirely
```

#### S2 — Hardcoded Credentials

```yaml
# CURRENT — credentials in source control
POSTGRES_PASSWORD: ids_password

# FIXED — reference .env file
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
```

Add to `.env` (gitignored):
```
POSTGRES_PASSWORD=<strong-random-password>
MONGO_ROOT_PASSWORD=<strong-random-password>
REDIS_PASSWORD=<strong-random-password>
```

#### S3 — X-Forwarded-For Spoofing

```python
# CURRENT — trusts any X-Forwarded-For header
def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
```

An attacker can set `X-Forwarded-For: 127.0.0.1` to bypass rate limiting.

```python
# FIXED — only trust X-Forwarded-For from known proxy IPs
TRUSTED_PROXIES = {"172.20.0.0/16"}  # Docker network

def _client_ip(request: Request) -> str:
    client_host = request.client.host if request.client else "unknown"
    if _is_trusted_proxy(client_host):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return client_host
```

#### S4 — No HTTPS in Dockerfile

The Dockerfile exposes port 8000 (HTTP). The Nginx config is referenced in docker-compose.yml but the `nginx/nginx.conf` file is not in the repository.

**Fix:** Include a working `nginx/nginx.conf` with TLS termination, or document that HTTPS is handled by the deployment environment.

#### S5 — WebSocket Unauthenticated

All security alerts are broadcast to any WebSocket client. For a graduation demo this is acceptable. Document it explicitly.

---

## 12. Lifecycle Management

> 💡 **Section này trả lời câu hỏi:** "Khi app khởi động, thứ tự khởi tạo là gì? Khi app tắt, thứ tự cleanup là gì? Nếu PostgreSQL chưa sẵn sàng khi app start, chuyện gì xảy ra?"
>
> **Quan trọng cho debugging:** Nếu app crash khi startup, đọc startup order diagram bên dưới để biết bước nào fail.

### Startup Order Dependencies

```mermaid
graph TD
    A[Uvicorn starts] --> B[main.py imports]
    B --> C[get_settings() — validates config]
    C --> D[FastAPI app created]
    D --> E[Middleware registered]
    E --> F[Routers registered]
    F --> G[lifespan startup]
    G --> H[init_db() — create PostgreSQL tables]
    H --> I[get_broadcast_bridge()]
    I --> J[get_alert_manager()]
    J --> K[alert_manager.set_broadcast_bridge()]
    K --> L[bridge.start() — consumer task]
    L --> M[App ready — accepting requests]
```

### What Happens If a Dependency Fails at Startup

| Failure | Current Behavior | Recommended Behavior |
|---|---|---|
| PostgreSQL unreachable | `init_db()` raises, logged as error, app continues | Exit with error (DB is required) |
| Redis unreachable | `RedisCache._connect()` logs warning, cache disabled | Continue (Redis is optional) |
| MongoDB unreachable | `get_mongo_client()` raises on first use | Continue (MongoDB is optional) |
| Model file missing | `load_from_directory()` returns False, pipeline fails on start | Log warning at startup |
| Invalid CORS_ORIGINS | `sys.exit(1)` | ✅ Correct |
| Invalid secrets in production | `sys.exit(1)` | ✅ Correct |

### Shutdown Order

```mermaid
graph TD
    A[SIGTERM received] --> B[lifespan shutdown]
    B --> C{pipeline running?}
    C -->|yes| D[coordinator.stop()]
    D --> E[sniffer.stop() — join thread 5s]
    E --> F[flow_builder.cleanup_expired_flows()]
    C -->|no| G[skip]
    F --> H[pipeline_task.cancel()]
    G --> H
    H --> I[bridge.stop()]
    I --> J[drain remaining queue]
    J --> K[consumer task cancelled]
    K --> L[Uvicorn exits]
```

### Lifecycle Problem: Sniffer Thread Not Stoppable

Scapy's `sniff()` with no `stop_filter` runs forever. The `PacketSniffer.stop()` method sets `is_running = False` and joins the thread with a 5-second timeout. But `sniff()` doesn't check `is_running` — it only stops when the timeout expires (dry_run mode) or when the process exits.

In normal mode (`dry_run=False`), `sniff()` runs indefinitely. `stop()` sets the flag and joins with 5s timeout, but the thread may still be running after the join returns (the join just gives up after 5s).

**Fix:** Use Scapy's `AsyncSniffer` which supports `stop()`:

```python
from scapy.all import AsyncSniffer

self._async_sniffer = AsyncSniffer(
    iface=self.interface,
    prn=self._packet_handler,
    filter=self.filter_expr,
    store=False,
)
self._async_sniffer.start()

# To stop:
self._async_sniffer.stop()
```

`AsyncSniffer.stop()` sends a signal to the underlying capture thread and waits for it to finish cleanly.

---

## 13. Deployment Topology

### Current Docker Compose Topology

```mermaid
graph TB
    subgraph "Host Machine"
        subgraph "Docker Network: ids-network (bridge)"
            BE[ids-backend\nFastAPI + Uvicorn\n:8000]
            PG[ids-postgres\nPostgreSQL 14\n:5432]
            MG[ids-mongodb\nMongoDB 6\n:27017]
            RD[ids-redis\nRedis 7\n:6379]
            NG[ids-nginx\nNginx\n:80/:443]
        end
        VOL1[(postgres-data)]
        VOL2[(mongo-data)]
        VOL3[(redis-data)]
        MDIR[./models volume]
        LDIR[./logs volume]
    end

    INTERNET[Internet / Frontend] -->|HTTPS :443| NG
    NG -->|HTTP :8000| BE
    BE -->|TCP :5432| PG
    BE -->|TCP :27017| MG
    BE -->|TCP :6379| RD
    PG --- VOL1
    MG --- VOL2
    RD --- VOL3
    BE --- MDIR
    BE --- LDIR
```

### Port Exposure Analysis

| Port | Service | Exposed to Host | Risk |
|---|---|---|---|
| 8000 | FastAPI | Yes | Medium — should be behind Nginx only |
| 5432 | PostgreSQL | Yes | High — should not be exposed in production |
| 27017 | MongoDB | Yes | High — should not be exposed in production |
| 6379 | Redis | Yes | High — should not be exposed in production |
| 80/443 | Nginx | Yes | Low — intended |

**Fix for production:** Remove host port mappings for PostgreSQL, MongoDB, and Redis. Only Nginx should be accessible from outside the Docker network.

```yaml
# CURRENT — exposes DB to host
postgres:
  ports:
    - "5432:5432"

# FIXED — internal only
postgres:
  # no ports: section
  expose:
    - "5432"
```

### Volume Strategy

| Volume | Type | Purpose |
|---|---|---|
| `postgres-data` | Named volume | PostgreSQL data persistence |
| `mongo-data` | Named volume | MongoDB data persistence |
| `redis-data` | Named volume | Redis AOF persistence |
| `./backend` | Bind mount | Live code reload (dev only) |
| `./models` | Bind mount | ML model artifacts |
| `./logs` | Bind mount | Log file access from host |
| `./data` | Bind mount | Training data access |

**Problem:** The `./backend` bind mount is appropriate for development but should be removed in production. In production, code should be baked into the image.

---

## 14. Docker Compose Explanation

### Service-by-Service Breakdown

#### `ids-backend`

```yaml
build:
  context: .
  dockerfile: Dockerfile
cap_add:
  - NET_RAW    # Required for raw packet capture (Scapy)
  - NET_ADMIN  # Required for interface management
privileged: true  # ← REMOVE THIS (see S1)
volumes:
  - ./backend:/app/backend  # ← dev only, remove in production
  - ./models:/app/models    # ML model artifacts
  - ./logs:/app/logs        # Log output
```

The `NET_RAW` capability is essential — without it, Scapy cannot open a raw socket for packet capture. This is why the container needs elevated privileges. `NET_RAW` alone is sufficient; `privileged: true` is overkill.

#### `postgres`

```yaml
image: postgres:14-alpine
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ids_user -d ids_db"]
  interval: 10s
  timeout: 5s
  retries: 5
```

The healthcheck is correct. The `depends_on` in `ids-backend` only waits for the container to start, not for PostgreSQL to be ready. The `healthcheck` + `depends_on: condition: service_healthy` pattern should be used:

```yaml
# FIXED
ids-backend:
  depends_on:
    postgres:
      condition: service_healthy
    mongodb:
      condition: service_healthy
    redis:
      condition: service_healthy
```

#### `mongodb`

```yaml
image: mongo:6-alpine
environment:
  MONGO_INITDB_ROOT_USERNAME: ids_mongo_user
  MONGO_INITDB_ROOT_PASSWORD: ids_mongo_pass  # ← hardcoded
```

The `mongosh` healthcheck command is correct for MongoDB 6. Note that `mongo:6-alpine` uses `mongosh` not `mongo` for the shell.

#### `redis`

```yaml
command: redis-server --requirepass ids_redis_pass --appendonly yes
```

`--appendonly yes` enables AOF persistence, which is correct for production. The password is hardcoded — should use `${REDIS_PASSWORD}`.

#### `nginx`

```yaml
volumes:
  - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
  - ./nginx/ssl:/etc/nginx/ssl:ro
```

The `nginx/` directory is not in the repository. This service will fail to start without it. Either include a working `nginx.conf` or make Nginx optional.

### Recommended `docker-compose.yml` Fixes

```yaml
# 1. Use healthcheck conditions
ids-backend:
  depends_on:
    postgres:
      condition: service_healthy
    mongodb:
      condition: service_healthy
    redis:
      condition: service_healthy

# 2. Remove privileged: true
# 3. Use env vars for credentials
# 4. Remove host port mappings for DBs in production
# 5. Remove ./backend bind mount in production
```

---

## 15. Testing Strategy

### Current Test Coverage

The project has tests in `backend/tests/`:

| Test File | What It Tests |
|---|---|
| `test_alerts.py` | Alert generation logic |
| `test_api_security.py` | API key auth, rate limiting |
| `test_db_integration.py` | PostgreSQL repository operations |
| `test_email_alerts.py` | Email service gating and dispatch |
| `test_feature_contract.py` | Feature name/order validation |
| `test_health_detailed.py` | Health check endpoints |
| `conftest.py` | Shared fixtures |

### Testing Gaps

1. **No pipeline integration test** — no test that runs the full packet → flow → feature → prediction → alert pipeline end-to-end
2. **No WebSocket test** — no test for the broadcast bridge
3. **No concurrency test** — no test for thread safety of FlowBuilder
4. **No load test integration** — Locust is in requirements but no test scripts are visible

### Recommended Test Structure

```
backend/tests/
├── unit/
│   ├── test_flow_builder.py       # Flow aggregation logic
│   ├── test_feature_extractor.py  # Feature computation
│   ├── test_predictor.py          # Inference with mock model
│   ├── test_alert_manager.py      # Alert gating, cooldown, correlation
│   └── test_rate_limiter.py       # Rate limit sliding window
├── integration/
│   ├── test_pipeline.py           # Full pipeline with dry_run
│   ├── test_db_integration.py     # Repository operations (existing)
│   └── test_websocket.py          # WebSocket broadcast
├── api/
│   ├── test_api_security.py       # Auth, rate limiting (existing)
│   ├── test_sniffer_routes.py     # Start/stop/status
│   └── test_alert_routes.py       # CRUD operations
└── conftest.py
```

### Key Test Patterns

#### Testing the Pipeline with Dry Run

```python
# test_pipeline.py
import pytest
from backend.pipeline.coordinator import PipelineCoordinator

@pytest.mark.asyncio
async def test_pipeline_dry_run():
    coordinator = PipelineCoordinator(
        interface="lo",  # loopback
        dry_run=True,
        dry_run_duration=1.0,
    )
    await coordinator.start()
    stats = coordinator.get_stats()
    assert stats["processed_packets"] >= 0
```

#### Testing Thread Safety of FlowBuilder

```python
# test_flow_builder.py
import threading
from backend.flow_engine.flow_builder import FlowBuilder

def test_concurrent_add_packet():
    fb = FlowBuilder()
    errors = []

    def add_packets():
        for i in range(1000):
            try:
                fb.add_packet({
                    "src_ip": f"10.0.0.{i % 255}",
                    "dst_ip": "192.168.1.1",
                    "src_port": 1024 + i,
                    "dst_port": 80,
                    "protocol": "tcp",
                    "length": 100,
                })
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=add_packets) for _ in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert len(errors) == 0, f"Thread safety errors: {errors}"
```

### Running Tests

```bash
# All tests
pytest backend/tests/ -v

# With coverage
pytest backend/tests/ --cov=backend --cov-report=html

# Skip slow integration tests
pytest backend/tests/ -v -m "not integration"

# Single test file
pytest backend/tests/test_feature_contract.py -v
```

---

## 16. Failure Recovery Strategy

### Service Failure Scenarios

#### PostgreSQL Unavailable

**Current behavior:** `init_db()` logs an error but the app continues. The first DB write (on attack detection) will raise an exception, which is caught and logged. The pipeline continues running but no data is persisted.

**Recommended behavior:** 
- At startup: retry with exponential backoff (3 attempts), then exit
- During operation: log error, continue pipeline, queue writes for retry

```python
# Startup retry pattern
import time

def init_db_with_retry(max_retries=3, delay=2.0):
    for attempt in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"DB init failed (attempt {attempt+1}): {e}. Retrying in {delay}s...")
            time.sleep(delay)
            delay *= 2
```

#### Redis Unavailable

**Current behavior:** `RedisCache._connect()` logs a warning, `redis_client = None`. All Redis operations check `is_connected()` and fall back to in-memory. This is correct and resilient.

**No change needed** — the fallback is already implemented.

#### MongoDB Unavailable

**Current behavior:** `log_flow_summary()` catches all exceptions and logs a warning. MongoDB failure is non-blocking.

**No change needed** — MongoDB is used for optional logging only.

#### Model File Missing

**Current behavior:** `load_from_directory()` returns `False`. `PipelineCoordinator.initialize()` raises `RuntimeError("Model not found")`. The pipeline fails to start.

**Recommended behavior:** This is correct. The pipeline cannot run without a model. The error message should include the expected file path.

#### WebSocket Client Disconnects

**Current behavior:** `ConnectionManager.broadcast()` catches exceptions per connection and removes disconnected clients. This is correct.

#### Sniffer Thread Crashes

**Current behavior:** `_run_sniffer()` catches exceptions, sets `is_running = False`, and logs the error. The pipeline coordinator's `while self.is_running` loop will exit on the next iteration.

**Problem:** There is no automatic restart. If the sniffer crashes (e.g. interface goes down), the pipeline stops silently. The `/health` endpoint will show `pipeline_running: false` but no alert is raised.

**Fix:** Add a watchdog in the coordinator's async loop:

```python
async def start(self) -> None:
    ...
    while self.is_running:
        await asyncio.sleep(1)
        # Watchdog: restart sniffer if it died unexpectedly
        if self.sniffer and not self.sniffer.is_running and self.is_running:
            logger.warning("Sniffer thread died unexpectedly, restarting...")
            self.sniffer.start()
```

---

## 17. Monitoring & Metrics Strategy

### Current Prometheus Metrics

The `monitoring/metrics.py` file defines Prometheus counters, histograms, and gauges, but **none of them are actually incremented anywhere in the codebase**. The metrics are defined but never called.

```python
# Defined but never called:
packets_captured_total.inc()
flows_processed_total.inc()
predictions_total.labels(...).inc()
alerts_total.labels(...).inc()
```

**Fix:** Add metric tracking calls at the appropriate points:

```python
# In PipelineCoordinator.packet_callback():
from backend.monitoring.metrics import packets_captured_total, predictions_total
packets_captured_total.inc()

# After inference:
predictions_total.labels(predicted_class=attack_type).inc()

# In AlertManager.generate_alert():
from backend.monitoring.metrics import alerts_total
alerts_total.labels(attack_type=attack_type, severity=adjusted_severity).inc()
```

### Recommended Metrics to Track

| Metric | Type | Labels | Where to Increment |
|---|---|---|---|
| `packets_captured_total` | Counter | — | `packet_callback()` |
| `flows_active` | Gauge | — | `FlowBuilder.get_stats()` |
| `predictions_total` | Counter | `predicted_class` | After `predict_flow()` |
| `alerts_total` | Counter | `attack_type`, `severity` | `generate_alert()` |
| `alert_queue_size` | Gauge | — | `bridge.get_stats()` |
| `ws_connections_active` | Gauge | — | `connect()` / `disconnect()` |
| `db_write_errors_total` | Counter | `operation` | DB exception handlers |
| `inference_duration_seconds` | Histogram | `model_name` | Around `predict_flow()` |

### Log Strategy

The project uses `python-json-logger` for structured JSON logs. This is correct for production. Key log events to ensure are present:

| Event | Level | Where |
|---|---|---|
| Pipeline started/stopped | INFO | `coordinator.py` |
| Attack detected | WARNING | `coordinator.py` |
| Alert generated | INFO | `alert_manager.py` |
| Alert suppressed (cooldown) | DEBUG | `alert_manager.py` |
| DB write error | ERROR | `repository.py` |
| WebSocket client connected | INFO | `websocket.py` |
| Model loaded | INFO | `model_loader.py` |
| Packet queue full | WARNING | `packet_sniffer.py` |

### Health Check Endpoints

| Endpoint | Purpose | Auth Required |
|---|---|---|
| `GET /health` | Basic liveness (pipeline running) | No |
| `GET /health/detailed` | All service connectivity | No |
| `GET /metrics` | Prometheus metrics | No (consider adding) |

**Recommendation:** Add auth to `/metrics` in production to prevent metric scraping by unauthorized clients.

---

## 18. Performance Bottlenecks

### Bottleneck Map

```mermaid
graph LR
    A[Packet arrives] -->|~0.01ms| B[_packet_handler]
    B -->|~0.1ms| C[FlowBuilder.add_packet]
    C -->|~1ms| D[FeatureExtractor]
    D -->|~2-5ms| E[Predictor.predict_flow]
    E -->|~5-20ms| F[DB writes × 4]
    F -->|~0.1ms| G[bridge.enqueue_alert]

    style F fill:#ff6b6b,color:#fff
    style E fill:#ffa94d,color:#fff
```

### Bottleneck 1: ML Inference (2-5ms per flow)

scikit-learn RandomForest inference on a 20-feature vector takes ~1-3ms. XGBoost is similar. TensorFlow LSTM is slower (~5-10ms). This is acceptable for graduation-project traffic volumes.

**At 1000 packets/second with 10% triggering inference:** 100 inferences/second × 3ms = 300ms of inference time per second on the sniffer thread. This means the sniffer thread is 30% busy with inference alone.

**Mitigation:** The `min_packets` threshold (default: 10) and `prediction_mode=once` ensure most packets don't trigger inference. This is the most important performance control.

### Bottleneck 2: Synchronous DB Writes (5-20ms per attack)

Each attack triggers 4 DB operations. At 5ms each = 20ms of DB I/O per attack on the sniffer thread. During a DDoS simulation, this is the primary bottleneck.

**Fix:** Async DB write queue (see Section 9).

### Bottleneck 3: `inter_arrival_times` List

For long-lived flows, this list grows without bound. `sum(list) / len(list)` in `get_stats()` is O(n) where n is the packet count. For a flow with 10,000 packets, this is 10,000 additions per `get_stats()` call.

**Fix:** Maintain a running mean:
```python
# Instead of storing all values:
self._iat_sum: float = 0.0
self._iat_count: int = 0

def add_packet(self, packet_info):
    ...
    if self.last_packet_time:
        iat = (self.last_seen - self.last_packet_time).total_seconds()
        self._iat_sum += iat
        self._iat_count += 1
    
@property
def inter_arrival_time_mean(self) -> float:
    return self._iat_sum / self._iat_count if self._iat_count > 0 else 0.0
```

### Bottleneck 4: `asyncio.to_thread()` per Poll Cycle

The broadcast bridge spawns a thread every 0.25 seconds to poll the queue. Under high alert volume, this creates many short-lived threads.

**Fix:** Use `asyncio.Queue` (see Section 7).

### Performance Tuning Parameters

| Parameter | Default | Effect |
|---|---|---|
| `min_packets` | 10 | Higher = fewer inferences, less CPU |
| `prediction_mode` | `once` | `once` = 1 inference per flow, `window` = repeated |
| `prediction_interval_sec` | 5.0 | Only relevant in `window` mode |
| `flow_expire_sec` | 30 | Lower = less memory, more flow churn |
| `flow_max_lifetime_sec` | 60 | Hard cap on flow age |
| `processed_flow_retention_sec` | 45 | How long to keep processed flows |

---

## 19. Concurrency Risks

### Risk Matrix

| Risk | Severity | Likelihood | Current Mitigation | Fix |
|---|---|---|---|---|
| `FlowBuilder.flows` dict mutation race | HIGH | Medium | None | Add `threading.Lock` |
| Sniffer singleton reuse after stop | HIGH | Low | None | Reset singleton on stop |
| `get_coordinator()` mutation race | MEDIUM | Low | `is_running` check | Add lock |
| `attack_patterns` dict unbounded growth | MEDIUM | High | Correlation window cleanup | Prune empty keys |
| `_windows` rate limiter unbounded | LOW | Medium | None | Delete empty deques |
| Email dispatch from wrong thread | HIGH | High | None | Move to bridge consumer |
| DB writes on sniffer thread | HIGH | High | None | Async write queue |

### The Core Concurrency Problem

The system has two execution contexts:

1. **Sniffer thread** — runs `packet_callback()` synchronously, processes packets as fast as possible
2. **Event loop** — runs all async code, handles HTTP requests, WebSocket broadcasts

These two contexts share mutable state:
- `FlowBuilder.flows` — written by sniffer thread, read by HTTP routes
- `AlertManager.alert_history` — written by sniffer thread
- `AlertManager.attack_patterns` — written by sniffer thread
- `AlertManager.whitelist` — written by HTTP routes, read by sniffer thread

### FlowBuilder Thread Safety Fix

```python
# flow_builder.py — add lock
import threading

class FlowBuilder:
    def __init__(self, ...):
        self.flows: Dict[str, Flow] = {}
        self._lock = threading.Lock()
        ...

    def add_packet(self, packet_info: dict) -> Optional[Flow]:
        ...
        with self._lock:
            if flow_key in self.flows:
                flow = self.flows[flow_key]
            else:
                flow = Flow(src_ip, dst_ip, src_port, dst_port, protocol)
                self.flows[flow_key] = flow
                self.total_flows_created += 1
        
        flow.add_packet(packet_info)  # Flow itself is only accessed by one thread
        return flow

    def cleanup_expired_flows(self) -> List[Flow]:
        with self._lock:
            # ... existing cleanup logic
```

### AlertManager Whitelist Thread Safety

The whitelist is a `set` that is read on the sniffer thread and written on the HTTP thread. Python's GIL makes individual set operations atomic, but `add` + `remove` sequences are not. For a graduation project, this is acceptable. For production, use `threading.Lock`.

---

## 20. Refactor Roadmap

### Classification of Changes

```
🟢 SAFE    — isolated change, no behavior change, low risk
🟡 MEDIUM  — behavior change, needs testing, medium risk
🔴 HIGH    — architecture change, needs migration plan, high risk
⚪ OPTIONAL — future improvement, not required for graduation
```

### Phase 0: Bug Fixes (do immediately, 1-2 hours)

| ID | Change | Risk | Files |
|---|---|---|---|
| C5 | Fix `NameError` in `get_alert_history()` | 🟢 | `alert_manager.py` |
| L3 | Remove duplicate `python-multipart` | 🟢 | `requirements.txt` |
| L1 | Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` | 🟢 | All files |
| L2 | Replace `declarative_base()` with `DeclarativeBase` | 🟢 | `database/models.py` |
| M5 | Remove `COPY .env.example .env` from Dockerfile | 🟢 | `Dockerfile` |

**Fix for C5:**
```python
# alert_manager.py — line ~180
def get_alert_history(self, ip_address: str) -> List[Dict]:
    if ip_address not in self.attack_patterns:
        return []
    return self.attack_patterns[ip_address]  # was: src_ip
```

---

### Phase 1: Safety Fixes (1-2 days)

| ID | Change | Risk | Files |
|---|---|---|---|
| H2 | Remove `privileged: true` | 🟢 | `docker-compose.yml` |
| H3 | Use env vars for credentials | 🟢 | `docker-compose.yml`, `.env` |
| H4 | Set `api_reload: bool = False` | 🟢 | `config.py` |
| H6 | Add `threading.Lock` to `FlowBuilder` | 🟡 | `flow_engine/flow_builder.py` |
| C3 | Add lock to `get_coordinator()` | 🟡 | `pipeline/coordinator.py` |
| M3 | Prune empty deques in rate limiter | 🟢 | `api/middleware/rate_limit.py` |
| M2 | Prune empty keys in `attack_patterns` | 🟢 | `alert_engine/alert_manager.py` |

**Fix for H6 (FlowBuilder lock):**
```python
import threading

class FlowBuilder:
    def __init__(self, ...):
        self._lock = threading.Lock()
        self.flows: Dict[str, Flow] = {}
        ...

    def add_packet(self, packet_info: dict) -> Optional[Flow]:
        src_ip = packet_info.get("src_ip")
        dst_ip = packet_info.get("dst_ip")
        if not src_ip or not dst_ip:
            return None
        src_port = packet_info.get("src_port")
        dst_port = packet_info.get("dst_port")
        protocol = packet_info.get("protocol", "unknown")
        flow_key = self._generate_flow_key(src_ip, dst_ip, src_port, dst_port, protocol)

        with self._lock:
            if flow_key not in self.flows:
                flow = Flow(src_ip, dst_ip, src_port, dst_port, protocol)
                self.flows[flow_key] = flow
                self.total_flows_created += 1
            else:
                flow = self.flows[flow_key]

        flow.add_packet(packet_info)
        return flow

    def cleanup_expired_flows(self) -> List[Flow]:
        current_time = datetime.utcnow()
        expired_keys: List[str] = []
        removed_flows: List[Flow] = []

        with self._lock:
            for flow_key, flow in list(self.flows.items()):
                # ... expiry checks ...
                if reason:
                    expired_keys.append(flow_key)
                    removed_flows.append(flow)
            for key in expired_keys:
                del self.flows[key]

        return removed_flows
```

---

### Phase 2: Performance & Correctness (2-3 days)

| ID | Change | Risk | Files |
|---|---|---|---|
| C2 | Move email dispatch to bridge consumer | 🟡 | `alert_manager.py`, `websocket.py`, `notifications/email.py` |
| M1 | Replace `inter_arrival_times` list with running mean | 🟡 | `flow_engine/flow_builder.py` |
| M4 | Fix double scaler application | 🟡 | `detection_engine/model_loader.py` |
| 5.6 | Remove duplicate feature extraction in `predict_flow()` | 🟡 | `detection_engine/predictor.py` |
| ~~H1~~ | ~~Initialize Alembic migrations~~ ✅ ĐÃ FIX | — | `backend/alembic/versions/001_initial_schema.py` |

**Fix for C2 (email in bridge consumer):**
```python
# websocket.py — AlertBroadcastBridge._dispatch()
async def _dispatch(self, message: Dict[str, Any]) -> None:
    try:
        await self._manager.broadcast(message)
        self.broadcast_total += 1
        # Dispatch email here — we're on the event loop
        if message.get("type") == "alert":
            from backend.notifications.email import email_service
            email_service.dispatch_alert_email(message["data"])
    except Exception as exc:
        logger.error("Failed to broadcast queued message: %s", exc)

# alert_manager.py — remove email dispatch from generate_alert()
# Delete these lines:
# if self.enable_email:
#     email_service.dispatch_alert_email(alert)
```

**Fix for M1 (running mean):**
```python
# flow_builder.py — Flow class
class Flow:
    def __init__(self, ...):
        # Replace:
        # self.inter_arrival_times: List[float] = []
        # With:
        self._iat_sum: float = 0.0
        self._iat_count: int = 0

    def add_packet(self, packet_info: dict) -> None:
        ...
        if self.last_packet_time:
            iat = (self.last_seen - self.last_packet_time).total_seconds()
            self._iat_sum += iat
            self._iat_count += 1
        ...

    def get_stats(self) -> dict:
        iat_mean = self._iat_sum / self._iat_count if self._iat_count > 0 else 0.0
        return {
            ...
            "inter_arrival_time_mean": iat_mean,
            ...
        }
```

---

### Phase 3: Architecture Improvements (3-5 days)

| ID | Change | Risk | Files |
|---|---|---|---|
| C1 | Async DB write queue | 🔴 | `pipeline/coordinator.py`, `alert_manager.py`, new `pipeline/db_writer.py` |
| C4 | Fix flow_key upsert | 🟡 | `database/repository.py` |
| 5.3 | Replace `sniff()` with `AsyncSniffer` | 🟡 | `capture_engine/packet_sniffer.py` |
| 7 | Replace `asyncio.to_thread` bridge with `asyncio.Queue` | 🟡 | `api/websocket.py` |
| H5 | Close MongoDB in lifespan shutdown | 🟢 | `main.py`, `database/connection.py` |

**Fix for C1 (async DB write queue):**
```python
# pipeline/db_writer.py — new file
import asyncio
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class AsyncDBWriter:
    """Receives DB write jobs from the sniffer thread and processes them on the event loop."""

    def __init__(self, maxsize: int = 50_000):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._task: asyncio.Task | None = None
        self.written_total = 0
        self.dropped_total = 0
        self.error_total = 0

    def enqueue(self, job: Dict[str, Any]) -> bool:
        try:
            self._queue.put_nowait(job)
            return True
        except asyncio.QueueFull:
            self.dropped_total += 1
            logger.warning("DB write queue full, dropping job type=%s", job.get("type"))
            return False

    async def start(self):
        self._task = asyncio.create_task(self._writer_loop(), name="db-writer")

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _writer_loop(self):
        while True:
            job = await self._queue.get()
            try:
                await asyncio.to_thread(self._write_sync, job)
                self.written_total += 1
            except Exception as exc:
                self.error_total += 1
                logger.error("DB write error: %s", exc)

    @staticmethod
    def _write_sync(job: Dict[str, Any]):
        from backend.database.connection import SessionLocal
        from backend.database.repository import (
            TrafficFlowRepository, FlowFeatureRepository,
            AttackAlertRepository, AttackHistoryRepository
        )
        db = SessionLocal()
        try:
            if job["type"] == "flow_alert":
                flow = TrafficFlowRepository.create_flow(db, job["flow"])
                FlowFeatureRepository.create_feature(db, job["features"], flow.id)
                AttackAlertRepository.create_alert(db, job["alert"], flow.id)
                AttackHistoryRepository.update_or_create_history(
                    db, job["alert"]["src_ip"],
                    job["alert"]["attack_type"],
                    job["alert"]["severity"]
                )
        finally:
            db.close()
```

---

## 21. Incremental Migration Plan

This plan avoids big-bang rewrites. Each phase is independently deployable and testable.

### Phase 0: Bug Fixes (Day 1, ~2 hours)

**Goal:** Fix known bugs that will cause runtime errors.

**Scope:**
- Fix `NameError` in `alert_manager.get_alert_history()`
- Remove duplicate `python-multipart` from requirements
- Replace `datetime.utcnow()` with timezone-aware equivalent

**Risk:** 🟢 Very low — isolated fixes  
**Rollback:** Git revert  
**Testing:** Run existing test suite, verify no regressions  
**Estimated complexity:** Trivial

```bash
# Verify fix
pytest backend/tests/ -v -k "alert"
```

---

### Phase 1: Security & Deployment Hardening (Day 1-2, ~4 hours)

**Goal:** Fix security issues before any demo or deployment.

**Scope:**
- Remove `privileged: true` from docker-compose.yml
- Move credentials to `.env` file
- Set `api_reload: False` as default
- Add `depends_on: condition: service_healthy` to docker-compose.yml

**Risk:** 🟢 Low — configuration changes only  
**Rollback:** Git revert docker-compose.yml  
**Testing:** `docker compose up`, verify all services start and connect  
**Estimated complexity:** Low

---

### Phase 2: Thread Safety (Day 2-3, ~6 hours)

**Goal:** Eliminate race conditions in shared mutable state.

**Scope:**
- Add `threading.Lock` to `FlowBuilder`
- Add lock to `get_coordinator()` singleton mutation
- Prune empty deques in rate limiter
- Prune empty keys in `attack_patterns`

**Risk:** 🟡 Medium — changes to hot path code  
**Rollback:** Feature flag: `ENABLE_FLOW_LOCK=true/false`  
**Testing:** Run concurrency test (see Section 15), load test with Locust  
**Estimated complexity:** Medium

---

### Phase 3: Email Fix (Day 3, ~2 hours)

**Goal:** Fix email dispatch from wrong thread context.

**Scope:**
- Remove email dispatch from `AlertManager.generate_alert()`
- Add email dispatch to `AlertBroadcastBridge._dispatch()`

**Risk:** 🟡 Medium — changes alert pipeline behavior  
**Rollback:** Revert both files  
**Testing:** `test_email_alerts.py`, verify emails still sent for high/critical alerts  
**Estimated complexity:** Low

---

### Phase 4: Memory Leak Fixes (Day 4, ~4 hours)

**Goal:** Fix unbounded memory growth.

**Scope:**
- Replace `inter_arrival_times` list with running mean in `Flow`
- Fix double scaler application in `ModelLoader`
- Remove duplicate feature extraction in `predict_flow()`

**Risk:** 🟡 Medium — changes feature computation (verify values unchanged)  
**Rollback:** Revert `flow_builder.py` and `predictor.py`  
**Testing:** `test_feature_contract.py`, compare feature values before/after  
**Estimated complexity:** Medium

---

### Phase 5: Async DB Writes (Day 5-7, ~1-2 days)

**Goal:** Remove synchronous DB writes from the sniffer thread.

**Scope:**
- Create `pipeline/db_writer.py` with `AsyncDBWriter`
- Register `AsyncDBWriter` in lifespan
- Replace direct DB calls in `coordinator.py` and `alert_manager.py` with `db_writer.enqueue()`
- Update `main.py` lifespan to start/stop `AsyncDBWriter`

**Risk:** 🔴 High — changes persistence behavior  
**Rollback:** Feature flag: `ASYNC_DB_WRITES=true/false`  
**Testing:** Integration test: verify all DB records are created correctly after pipeline run  
**Estimated complexity:** High

**Migration strategy:**
1. Implement `AsyncDBWriter` with tests
2. Add `ASYNC_DB_WRITES` env var (default: `false`)
3. Deploy with `ASYNC_DB_WRITES=false` (old behavior)
4. Run load test, verify no data loss
5. Switch to `ASYNC_DB_WRITES=true`
6. Monitor DB write queue size and error rate

---

### Phase 6: Alembic Migrations (Day 7-8, ~4 hours)

**Goal:** Replace `create_all()` with proper schema migrations.

**Scope:**
- Initialize Alembic: `alembic init alembic`
- Configure `alembic.ini` and `env.py` to use the same `engine`
- Generate initial migration: `alembic revision --autogenerate -m "initial"`
- Apply migration: `alembic upgrade head`
- Fix `flow_key` upsert in `TrafficFlowRepository`

**Risk:** 🔴 High — changes database schema management  
**Rollback:** `alembic downgrade -1`  
**Testing:** Run migration on a test database, verify all tables created correctly  
**Estimated complexity:** Medium

---

### Phase 7: Optional Improvements (Post-graduation)

These are improvements that go beyond graduation-project scope but are worth documenting for future work.

| Improvement | Benefit | Complexity |
|---|---|---|
| Replace `asyncio.to_thread` bridge with `asyncio.Queue` | Fewer threads, cleaner code | Low |
| Replace `sniff()` with `AsyncSniffer` | Cleaner shutdown | Medium |
| Add WebSocket authentication | Security | Low |
| Add Alembic auto-migration on startup | Operational convenience | Low |
| Add Prometheus metric instrumentation | Observability | Medium |
| Add request ID / correlation ID middleware | Debugging | Low |
| Separate `requirements-dev.txt` | Smaller production image | Low |

---

## 22. Production Recommendations

### Minimum Viable Production Checklist

```
Infrastructure:
[ ] Remove privileged: true from docker-compose.yml
[ ] Move all credentials to .env (gitignored)
[ ] Remove host port mappings for PostgreSQL, MongoDB, Redis
[ ] Add depends_on: condition: service_healthy
[ ] Include working nginx/nginx.conf with TLS
[ ] Remove ./backend bind mount (bake code into image)

Application:
[ ] Set ENVIRONMENT=production in .env
[ ] Set strong SECRET_KEY (>= 32 chars, random)
[ ] Set strong API_KEY (>= 16 chars, random)
[ ] Set CORS_ORIGINS to actual frontend domain
[ ] Set API_RELOAD=false
[ ] Fix NameError in get_alert_history()
[ ] Add threading.Lock to FlowBuilder

Database:
[ ] Initialize Alembic and run migrations
[ ] Set up PostgreSQL backup (pg_dump cron)
[ ] Set MongoDB authentication

Monitoring:
[ ] Verify /health/detailed returns all services connected
[ ] Add Prometheus metric instrumentation
[ ] Set up log rotation for logs/backend.log
```

### Uvicorn Production Command

```bash
# Development (current)
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Production (recommended)
uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --no-access-log \
  --log-level warning
```

**Why `--workers 1`:** The system uses module-level singletons (FlowBuilder, AlertManager, etc.) that are not safe to share across multiple worker processes. Multiple workers would each have their own independent state, causing split-brain behavior. Single worker is the correct choice for this architecture.

### Environment Variables Reference

```bash
# Required in production
ENVIRONMENT=production
SECRET_KEY=<random-64-char-string>
API_KEY=<random-32-char-string>
CORS_ORIGINS=https://your-frontend-domain.com

# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=ids_db
POSTGRES_USER=ids_user
POSTGRES_PASSWORD=<strong-password>

# MongoDB
MONGO_URI=mongodb://user:pass@mongodb:27017/ids_logs?authSource=admin
MONGO_DB=ids_logs

# Redis
REDIS_URL=redis://:password@redis:6379/0

# Email (optional)
ENABLE_EMAIL_ALERTS=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_TO=soc-team@example.com

# Pipeline tuning
MIN_PACKETS=10
PREDICTION_MODE=once
FLOW_EXPIRE_SEC=30
```

---

## 23. Graduation-Project Scope Decisions

This section documents deliberate architectural decisions that are appropriate for a graduation project but would be different in a production system. These are defensible in a thesis.

### Decision 1: Monolith over Microservices

**Decision:** Single FastAPI process with all components.  
**Why:** Microservices add operational complexity (service discovery, network latency, distributed tracing) that is not justified for a 1-3 person team. The monolith is easier to develop, test, and deploy.  
**Thesis defense:** "We chose a monolith-first architecture following the principle of starting simple and extracting services only when needed. The system is designed with clear module boundaries that would allow future extraction."

### Decision 2: Single Uvicorn Worker

**Decision:** `--workers 1` (single process).  
**Why:** Module-level singletons (FlowBuilder, AlertManager) are not safe for multi-process deployment. The packet capture thread is also per-process. Multiple workers would each capture packets independently, creating duplicate alerts.  
**Thesis defense:** "Single-worker deployment is appropriate for the graduation-project scope. Horizontal scaling would require replacing in-memory state with a shared store (Redis) and using a message queue for packet distribution."

### Decision 3: In-Memory Flow State

**Decision:** `FlowBuilder.flows` is an in-memory dict.  
**Why:** Storing flow state in Redis or PostgreSQL would add significant latency to the hot path (every packet). For a single-server deployment, in-memory is the correct choice.  
**Thesis defense:** "Flow state is maintained in memory for performance. The flow expiry mechanism prevents unbounded growth. In a distributed deployment, this would be replaced with a shared cache."

### Decision 4: Three Databases (PostgreSQL + MongoDB + Redis)

**Decision:** Use all three databases for different purposes.  
**Why:** Each database is used for what it does best:
- PostgreSQL: structured relational data (flows, alerts, models) with ACID guarantees
- MongoDB: unstructured flow log documents with flexible schema
- Redis: TTL-based cooldown keys with O(1) lookup

**Thesis defense:** "We use polyglot persistence, selecting the appropriate database for each data type. This demonstrates understanding of database trade-offs."

### Decision 5: Synchronous DB Writes (Current State)

**Decision:** DB writes happen on the sniffer thread (current, known issue).  
**Why:** Simpler to implement. For graduation-project traffic volumes (lab environment), the latency is acceptable.  
**Thesis defense:** "We identified synchronous DB writes as a performance bottleneck and documented the fix (async write queue). The current implementation is sufficient for the graduation demo environment."

### Decision 6: No Authentication on WebSocket

**Decision:** `/ws` endpoint is public.  
**Why:** Simplifies the frontend integration. The WebSocket only broadcasts alerts (read-only), so the security risk is information disclosure, not system compromise.  
**Thesis defense:** "The WebSocket endpoint is intentionally public for the graduation demo. Production deployment would add token-based authentication."

### Decision 7: SHAP for XAI

**Decision:** Use SHAP TreeExplainer for explainability.  
**Why:** SHAP provides theoretically grounded feature attributions (Shapley values). TreeExplainer is fast for tree-based models. This is a strong choice for a thesis.  
**Thesis defense:** "We use SHAP (SHapley Additive exPlanations) to provide interpretable explanations for model predictions. This addresses the 'black box' criticism of ML-based IDS systems."

---

## Appendix A: File Change Summary

| File | Issues | Priority | Estimated Effort |
|---|---|---|---|
| `alert_engine/alert_manager.py` | C1, C2, C5, M2 | Critical | 4h |
| `flow_engine/flow_builder.py` | H6, M1 | High | 3h |
| `pipeline/coordinator.py` | C1, C3 | Critical | 4h |
| `api/websocket.py` | C2 (email) | High | 2h |
| `detection_engine/predictor.py` | M4, 5.6 | Medium | 2h |
| `detection_engine/model_loader.py` | M4 | Medium | 1h |
| `capture_engine/packet_sniffer.py` | 5.3 (singleton) | High | 2h |
| `database/connection.py` | H5 | Medium | 1h |
| `database/repository.py` | C4 | Medium | 2h |
| `database/models.py` | L2 | Low | 1h |
| `config.py` | H4, L3 | Low | 0.5h |
| `api/middleware/rate_limit.py` | M3, S3 | Medium | 1h |
| `docker-compose.yml` | H2, H3, S1 | Critical | 1h |
| `Dockerfile` | M5 | Medium | 0.5h |
| `requirements.txt` | L3, L8 | Low | 0.5h |
| `monitoring/metrics.py` | Unused metrics | Medium | 3h |
| `main.py` | H4, lifecycle | Low | 1h |

**Total estimated effort for all fixes:** ~30 hours (1 week for 1 developer)

---

## Appendix B: Dependency Graph

```mermaid
graph TD
    main --> config
    main --> database/connection
    main --> api/websocket
    main --> alert_engine/alert_manager
    main --> api/routes/sniffer
    main --> api/legacy_routes
    main --> api/routes/traffic
    main --> api/routes/xai
    main --> monitoring/metrics

    api/routes/sniffer --> pipeline/coordinator
    api/routes/sniffer --> api/dependencies
    api/routes/sniffer --> api/validation

    pipeline/coordinator --> capture_engine/packet_sniffer
    pipeline/coordinator --> flow_engine/flow_builder
    pipeline/coordinator --> feature_engine/feature_extractor
    pipeline/coordinator --> detection_engine/model_loader
    pipeline/coordinator --> detection_engine/predictor
    pipeline/coordinator --> alert_engine/alert_manager
    pipeline/coordinator --> database/connection
    pipeline/coordinator --> database/repository
    pipeline/coordinator --> database/mongo_logger

    alert_engine/alert_manager --> database/connection
    alert_engine/alert_manager --> database/repository
    alert_engine/alert_manager --> notifications/email
    alert_engine/alert_manager --> cache/redis_cache

    detection_engine/predictor --> detection_engine/model_loader
    detection_engine/predictor --> feature_engine/feature_extractor
    detection_engine/predictor --> flow_engine/flow_builder

    api/legacy_routes --> database/connection
    api/legacy_routes --> alert_engine/alert_manager
    api/legacy_routes --> ml/models

    api/routes/xai --> ml/xai
    api/routes/xai --> detection_engine/predictor
```

---

## Appendix C: Quick Reference — Common Operations

### Start the System

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your settings

# 2. Start all services
docker compose up -d

# 3. Verify health
curl http://localhost:8000/health/detailed

# 4. Start packet capture (requires API key)
curl -X POST "http://localhost:8000/api/sniffer/start?interface=eth0" \
  -H "X-API-Key: your-api-key"

# 5. Check pipeline status
curl "http://localhost:8000/api/sniffer/status" \
  -H "X-API-Key: your-api-key"
```

### Stop the System

```bash
# Stop packet capture
curl -X POST "http://localhost:8000/api/sniffer/stop" \
  -H "X-API-Key: your-api-key"

# Stop all containers
docker compose down

# Stop and remove volumes (WARNING: deletes all data)
docker compose down -v
```

### View Alerts

```bash
# Get recent alerts
curl "http://localhost:8000/api/alerts/?limit=20"

# Get critical alerts only
curl "http://localhost:8000/api/alerts/?severity=critical"

# Resolve an alert
curl -X PUT "http://localhost:8000/api/alerts/{alert_id}/resolve" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Investigated, false positive"}'
```

### XAI Explanation

```bash
curl -X POST "http://localhost:8000/api/xai/explain" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "ensemble",
    "features": {
      "flow_duration": 1.5,
      "total_fwd_packets": 100,
      "total_bwd_packets": 50,
      "total_fwd_bytes": 15000,
      "total_bwd_bytes": 5000,
      "avg_packet_size": 133.3,
      "packet_rate": 100.0,
      "byte_rate": 13333.3,
      "syn_count": 1,
      "fin_count": 1,
      "rst_count": 0,
      "psh_count": 10,
      "ack_count": 148,
      "unique_dst_ports": 1,
      "inter_arrival_time_mean": 0.01,
      "fwd_packet_rate": 66.7,
      "bwd_packet_rate": 33.3,
      "fwd_byte_rate": 10000.0,
      "bwd_byte_rate": 3333.3,
      "packet_length_mean": 133.3
    }
  }'
```

---

*This document was generated by analyzing the complete source code of the Z-Sentinel IDS graduation project. All issues, recommendations, and code examples are based on the actual implementation.*

*Last updated: May 2026*
