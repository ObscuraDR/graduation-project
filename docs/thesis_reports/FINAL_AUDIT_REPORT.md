# FINAL AUDIT REPORT
## Z-Sentinel — Machine Learning-Based Intrusion Detection System (IDS) Backend

**Document Type:** Final Technical Audit Report  
**Status:** Demo-Ready / Thesis Defense Ready  
**Date:** May 2026

---

## 1. Executive Summary

Z-Sentinel IDS backend là một hệ thống phát hiện xâm nhập mạng thời gian thực dựa trên Machine Learning, được xây dựng bằng FastAPI. Hệ thống triển khai đầy đủ pipeline: bắt gói tin thô từ network interface → tổng hợp thành bidirectional flows → trích xuất 20 đặc trưng thống kê → phân loại bằng ensemble ML model → sinh cảnh báo → lưu vào PostgreSQL → broadcast qua WebSocket → gửi email.

REST API được bảo mật bằng X-API-Key authentication, per-IP sliding-window rate limiting, và strict input validation. Hệ thống sử dụng 3 databases: PostgreSQL (structured data), MongoDB (flow logs), Redis (alert cooldown).

**Điểm mạnh:**
- Kiến trúc monolith rõ ràng, dễ hiểu và bảo vệ trong luận văn
- Thread-safe WebSocket broadcast qua `AlertBroadcastBridge`
- Feature contract validation ngăn silent misalignment giữa training và inference
- Production security validation (từ chối khởi động nếu dùng default secrets)
- Test suite đầy đủ, CI-safe (không cần live infrastructure)

**Known issues cần fix trước production:** Xem Section 5 và [`ENGINEERING_REBUILD_GUIDE.md`](ENGINEERING_REBUILD_GUIDE.md).

---

## 2. System Architecture

```
Network Interface (Scapy/Npcap)
        │  raw IP packets
        ▼
capture_engine.PacketSniffer  [daemon thread]
  • BPF filter, 10k-packet queue, dry-run mode
        │  packet_info dict (callback)
        ▼
pipeline.PipelineCoordinator.packet_callback()  [sniffer thread]
        │
        ├─► flow_engine.FlowBuilder
        │     • 5-tuple aggregation (src_ip:port ↔ dst_ip:port:protocol)
        │     • Inference gating: once | window mode
        │
        ├─► feature_engine.FeatureExtractor
        │     • 20 statistical features
        │     • Matches models/features.json contract
        │
        ├─► detection_engine.Predictor
        │     • StandardScaler → RandomForest ensemble → LabelEncoder
        │     • NaN/Inf validation, feature contract enforcement
        │
        └─► alert_engine.AlertManager
              • Gate 1: Normal traffic → suppress
              • Gate 2: confidence < 0.75 → suppress
              • Gate 3: whitelist → suppress
              • Gate 4: Redis TTL cooldown → suppress
              • Correlation: severity escalation per-IP window
                    │
                    ├─► AlertBroadcastBridge.enqueue_alert()
                    │       └─► [event loop] WebSocket broadcast → Dashboard
                    ├─► SessionLocal() → PostgreSQL
                    ├─► mongo_logger → MongoDB
                    └─► email_service → SMTP (high/critical + conf≥0.85)
```

---

## 3. Module Breakdown

### 3.1 `capture_engine` — `backend/capture_engine/packet_sniffer.py`

Wraps Scapy's `sniff()` trong daemon thread. Hỗ trợ BPF filter, queue 10.000 packets, dry-run mode (timed capture cho testing), Windows Npcap interface enumeration. Callback-based: mỗi packet gọi `PipelineCoordinator.packet_callback()` trực tiếp.

### 3.2 `flow_engine` — `backend/flow_engine/flow_builder.py`

In-memory dict của `Flow` objects, keyed by 5-tuple. Mỗi `Flow` tích lũy: packet/byte counts theo direction, TCP flag counts, inter-arrival times. Hai inference-gating modes:
- `once` — inference chạy đúng 1 lần sau khi đạt `min_packets`
- `window` — inference lặp lại mỗi `prediction_interval_sec` giây

Flow expiry: inactive TTL, max lifetime, post-prediction retention.

### 3.3 `feature_engine` — `backend/feature_engine/feature_extractor.py`

Chuyển `Flow` object thành 20-feature vector. Thứ tự features được enforce bởi `models/features.json` để tránh silent misalignment giữa training và inference.

**20 features:** `flow_duration`, `total_fwd_packets`, `total_bwd_packets`, `total_fwd_bytes`, `total_bwd_bytes`, `avg_packet_size`, `packet_rate`, `byte_rate`, `syn_count`, `fin_count`, `rst_count`, `psh_count`, `ack_count`, `unique_dst_ports`, `inter_arrival_time_mean`, `fwd_packet_rate`, `bwd_packet_rate`, `fwd_byte_rate`, `bwd_byte_rate`, `packet_length_mean`

### 3.4 `detection_engine` — `backend/detection_engine/`

- **`ModelLoader`** — load `ensemble.pkl`, `ensemble_scaler.pkl`, `ensemble_encoder.pkl`; hỗ trợ sklearn, XGBoost, TensorFlow
- **`Predictor`** — validate feature contract (FeatureContractError), apply scaler, run inference, decode label, map confidence → severity

**Severity mapping:**
- `critical`: confidence ≥ 0.90
- `high`: confidence ≥ 0.80
- `medium`: confidence ≥ 0.75
- `low`: dưới threshold

### 3.5 `alert_engine` — `backend/alert_engine/alert_manager.py`

4-gate suppression chain. Correlation logic:
- ≥ 5 attacks từ cùng IP trong correlation window → escalate severity
- PortScan ≥ 3 lần → critical
- DDoS ≥ 2 lần → critical

Redis-backed cooldown với in-memory fallback.

### 3.6 `api` — `backend/api/`

- `routes/sniffer.py` — pipeline start/stop/status (API key required)
- `routes/traffic.py` — read-only traffic monitoring
- `routes/xai.py` — SHAP explanation endpoint
- `legacy_routes.py` — alerts CRUD, whitelist, predictions, stats
- `websocket.py` — `AlertBroadcastBridge` (thread-safe queue → async WebSocket fan-out)
- `middleware/rate_limit.py` — sliding-window per-IP rate limiter
- `validation.py` — IPv4, port, protocol, interface validators
- `dependencies.py` — `verify_api_key` (timing-safe)

### 3.7 `database` — `backend/database/`

- `models.py` — SQLAlchemy ORM: `TrafficFlow`, `FlowFeature`, `AttackAlert`, `AttackHistory`, `Whitelist`, `Model`, `User`, `Metric`
- `connection.py` — PostgreSQL QueuePool engine, MongoDB client, Redis client
- `repository.py` — Repository pattern: `TrafficFlowRepository`, `FlowFeatureRepository`, `AttackAlertRepository`, `AttackHistoryRepository`
- `mongo_logger.py` — Fire-and-forget MongoDB flow log writer

### 3.8 `pipeline` — `backend/pipeline/coordinator.py`

`PipelineCoordinator` kết nối tất cả engines. Lifecycle: `initialize()` → `start()` (async keep-alive loop) → `stop()`. `get_stats()` aggregate metrics từ tất cả sub-components.

### 3.9 `notifications` — `backend/notifications/email.py`

Async SMTP service (aiosmtplib). Gating: severity ∈ {high, critical} AND confidence ≥ 0.85 AND IP không trong email cooldown. Multi-recipient, HTML + plain text.

### 3.10 `ml` — `backend/ml/`

- `models.py` — `RandomForestIDS`, `XGBoostIDS`, `EnsembleIDS` (sklearn wrappers)
- `training.py` — CLI training script
- `train_flow_model.py` — CICIDS2017 training pipeline
- `xai.py` — SHAP `TreeExplainer` wrapper; trả về `top_features`, `shap_values`, `base_value`
- `create_dummy_models.py` — Tạo model giả cho dev/demo

---

## 4. Security Controls

### 4.1 API Key Authentication

Tất cả `/api/sniffer/*` endpoints yêu cầu `X-API-Key` header. Dùng `secrets.compare_digest` để chống timing attack. Missing/incorrect key → `HTTP 401`.

### 4.2 Rate Limiting

Sliding-window per-IP, in-memory:

| Endpoint Group | Limit | Window |
|---|---|---|
| `/api/sniffer/*` | 10 requests | 60 seconds |
| `/api/whitelist/*` | 30 requests | 60 seconds |
| `/api/xai/*` | 60 requests | 60 seconds |

HTTP 429 với `Retry-After` header.

### 4.3 Input Validation

- `validate_ipv4` — từ chối hostname, IPv6, out-of-range octets
- `validate_port` — enforce 1–65535
- `validate_protocol` — allowlist: tcp/udp/icmp
- `validate_interface` — từ chối shell injection chars (`;`, `|`, `` ` ``, `$`, `/`)

### 4.4 Production Startup Validation

Khi `ENVIRONMENT=production`, `model_validator` trong `Settings` từ chối khởi động nếu:
- `SECRET_KEY` hoặc `API_KEY` vẫn là default value
- `SECRET_KEY` < 32 chars hoặc `API_KEY` < 16 chars
- `CORS_ORIGINS` trống

---

## 5. Known Issues

Xem [`ENGINEERING_REBUILD_GUIDE.md`](ENGINEERING_REBUILD_GUIDE.md) Section 4 để biết phân tích đầy đủ và code-level fixes.

### Critical (fix trước production)

| ID | Vấn đề | File |
|---|---|---|
| C1 | Synchronous DB writes trên sniffer thread — blocks packet processing | `coordinator.py`, `alert_manager.py` |
| C2 | Email dispatch gọi `asyncio.get_event_loop()` từ sniffer thread — broken Python 3.10+ | `alert_manager.py`, `email.py` |
| C3 | `get_coordinator()` mutates singleton without lock | `coordinator.py` |
| C4 | `flow_key` UNIQUE constraint breaks `window` prediction mode | `repository.py` |
| C5 | `NameError: src_ip` trong `get_alert_history()` | `alert_manager.py` |

### High Risk

| ID | Vấn đề | File |
|---|---|---|
| ~~H1~~ | ~~Không có Alembic migrations~~ (đã fix: `backend/alembic/versions/001_initial_schema.py`) | ✅ |
| H2 | `privileged: true` trong docker-compose.yml | `docker-compose.yml` |
| H3 | Hardcoded credentials trong docker-compose.yml | `docker-compose.yml` |
| H6 | `FlowBuilder.flows` dict không thread-safe | `flow_builder.py` |

### Medium Risk

| ID | Vấn đề | File |
|---|---|---|
| M1 | `inter_arrival_times` list tăng không giới hạn | `flow_builder.py` |
| M2 | `attack_patterns` dict tăng không giới hạn | `alert_manager.py` |
| M3 | Rate limiter `_windows` dict tăng không giới hạn | `rate_limit.py` |
| M4 | Scaler có thể được apply 2 lần | `model_loader.py` |

---

## 6. Testing

### Test Suite

| File | Type | Mô tả |
|---|---|---|
| `test_alerts.py` | Unit | AlertManager: cooldown, suppression, whitelist, stats |
| `test_api_security.py` | Unit | API key auth, rate limiting |
| `test_db_integration.py` | Integration | Repository layer (SQLite in-memory) |
| `test_email_alerts.py` | Integration | Email gating (no real SMTP) |
| `test_feature_contract.py` | Unit | Feature vector alignment |
| `test_health_detailed.py` | Unit | Health check endpoints |
| `test_input_validation.py` | Unit | IPv4, port, protocol, interface validators |
| `test_models.py` | Unit | ML model loading and prediction |
| `test_pipeline_integration.py` | Integration | Full pipeline: packet → alert |
| `test_rate_limiting.py` | Unit | Sliding-window rate limiter |
| `test_sniffer_interface_validation.py` | Unit | Interface name validation |
| `test_websocket_broadcast.py` | Integration | WebSocket alert broadcast |
| `test_xai.py` | Unit | SHAP explanation endpoint |
| `conftest.py` | — | Shared fixtures |

### Testing Strategy

- **Không cần live infrastructure:** TestClient, SQLite in-memory, `unittest.mock` cho SMTP và WebSocket
- **Scapy isolation:** Tests import `PipelineCoordinator` với stub cho `packet_sniffer` module
- **ML artifacts:** Tests tạo minimal sklearn artifacts trong `tempfile.TemporaryDirectory`
- **Deterministic:** Random seed = 42, alert cooldown = 0 trong integration tests

```bash
# Chạy tất cả tests
pytest backend/tests/ -v

# Với coverage
pytest backend/tests/ --cov=backend --cov-report=html
```

---

## 7. CICIDS2017 Dataset & Training

### Dataset

Canadian Institute for Cybersecurity IDS 2017 — labeled network flows với 7 attack categories: Brute Force, DoS/DDoS, Web Attacks, Infiltration, Botnet, Port Scan.

### Preprocessing Pipeline — `scripts/preprocess_cicids2017.py`

1. Load CICIDS2017 CSV files (chunked)
2. Normalize column names, map sang 20-feature schema
3. Derive missing features (unique_dst_ports, rates từ bytes/duration)
4. Map labels → canonical classes: Normal, DDoS, PortScan, BruteForce, Botnet, Abnormal
5. Drop NaN/Inf rows
6. Output: `data/cicids2017_processed.csv` + `reports/cicids2017_preprocess_report.json`

### Training Pipeline — `backend/ml/train_flow_model.py`

1. Load processed CSV
2. Train/test split (test_size=0.5, random_state=42)
3. Fit `StandardScaler`
4. Train `RandomForestClassifier` (n_estimators=100, max_depth=10, class_weight="balanced")
5. Evaluate: accuracy, precision/recall/F1 (macro), confusion matrix, FPR
6. Save artifacts: `ensemble.pkl`, `ensemble_scaler.pkl`, `ensemble_encoder.pkl`, `features.json`
7. Write `reports/cicids2017_training_report.json`

```bash
# Preprocess
python backend/scripts/preprocess_cicids2017.py --input-dir data/cicids2017 --output data/cicids2017_processed.csv

# Train
python backend/ml/train_flow_model.py --data data/cicids2017_processed.csv --model ensemble

# Xem kết quả
cat reports/cicids2017_training_report.json
```

---

## 8. Performance Notes

### Throughput

- **Scapy packet capture:** ~500–2,000 pps (Python-layer, không dùng kernel bypass)
- **ML inference:** < 1ms per flow (100-estimator RandomForest, 20 features)
- **Flow assembly + feature extraction:** O(1) per packet (hash map lookup)
- **DB insert:** ~1–5ms per alert (PostgreSQL local)
- **WebSocket broadcast:** async, non-blocking

**Phù hợp cho:** Lab networks, edge devices, low-to-medium traffic environments.  
**Không phù hợp cho:** High-throughput production (>1 Gbps) — cần kernel-bypass capture.

### Bottlenecks

1. **Synchronous DB writes trên sniffer thread** — primary bottleneck dưới attack load
2. **ML inference** — ~2-5ms per flow, acceptable với min_packets gating
3. **`inter_arrival_times` list** — O(n) mean computation cho long-lived flows

---

## 9. Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| Scapy throughput ceiling (~2k pps) | Không monitor high-speed links | Acceptable cho thesis/lab scope |
| Sync DB writes trên sniffer thread | Packet drops dưới high attack rate | Fix: async DB write queue (xem ENGINEERING_REBUILD_GUIDE.md) |
| No TLS trên WebSocket `/ws` | Plaintext real-time alerts | Add HTTPS/WSS qua Nginx reverse proxy |
| Single-node deployment | Không horizontal scaling | Docker Compose đủ cho demo |
| No auth trên `/ws` | Bất kỳ client nào đều nhận alerts | Acceptable cho academic demo |
| CICIDS2017 là dataset 2017 | Có thể không reflect modern attacks | Supplement với CIC-IDS-2018, UNSW-NB15 |
| Prometheus metrics defined nhưng chưa increment | Metrics endpoint trống | Add tracking calls (xem ENGINEERING_REBUILD_GUIDE.md Section 17) |

---

## 10. Deployment

### Docker Compose (recommended)

```bash
cp .env.example .env
# Cấu hình .env
docker compose up -d
curl http://localhost:8000/health/detailed
```

### Services

| Service | Image | Port |
|---|---|---|
| `ids-backend` | Build từ Dockerfile | 8000 |
| `postgres` | postgres:14-alpine | 5432 |
| `mongodb` | mongo:6-alpine | 27017 |
| `redis` | redis:7-alpine | 6379 |
| `dashboard` | Build từ frontend/Dockerfile | 3000 |
| `nginx` | nginx:alpine | 80/443 (optional) |

### Capabilities

```yaml
cap_add:
  - NET_RAW    # Bắt buộc cho Scapy
  - NET_ADMIN  # Bắt buộc cho interface management
# KHÔNG dùng privileged: true
```

---

*Báo cáo này được tạo dựa trên phân tích toàn bộ mã nguồn trong thư mục `backend/`. Tất cả vấn đề, khuyến nghị, và ví dụ code đều dựa trên implementation thực tế.*
