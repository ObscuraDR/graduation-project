# Các Chức Năng Của Z-Sentinel IDS Backend

Tài liệu này mô tả đầy đủ các nhóm chức năng của hệ thống backend, dựa trên mã nguồn thực tế.

---

## 1. IDS Pipeline — Phát hiện xâm nhập thời gian thực

Đây là chức năng cốt lõi của hệ thống. Pipeline chạy hoàn toàn tự động sau khi được khởi động.

**Luồng xử lý:**
```
Gói tin mạng → PacketSniffer → FlowBuilder → FeatureExtractor → Predictor → AlertManager
```

**Chi tiết từng bước:**

| Bước | Module | Mô tả |
|---|---|---|
| Bắt gói tin | `capture_engine/packet_sniffer.py` | Scapy `sniff()` trong daemon thread, BPF filter, queue 10.000 packets |
| Tổng hợp flow | `flow_engine/flow_builder.py` | Gom packets theo 5-tuple (src_ip, dst_ip, src_port, dst_port, protocol) |
| Trích xuất đặc trưng | `feature_engine/feature_extractor.py` | 20 đặc trưng thống kê (rates, flags, timing) |
| Phân loại tấn công | `detection_engine/predictor.py` | ML inference với feature contract validation |
| Sinh cảnh báo | `alert_engine/alert_manager.py` | Cooldown, correlation, severity escalation |

**Điều khiển pipeline qua API:**
- `POST /api/sniffer/start` — Khởi động (yêu cầu X-API-Key)
- `POST /api/sniffer/stop` — Dừng (yêu cầu X-API-Key)
- `GET /api/sniffer/status` — Trạng thái và thống kê (yêu cầu X-API-Key)

**Inference gating** — Cơ chế tránh predict quá nhiều:
- `min_packets`: Số packet tối thiểu trước khi predict (default: 10)
- `prediction_mode=once`: Mỗi flow chỉ predict 1 lần
- `prediction_mode=window`: Predict lặp lại theo interval

---

## 2. Quản lý cảnh báo (Alerts)

**Sinh cảnh báo tự động** (từ pipeline):
- Confidence threshold gate: chỉ sinh alert khi confidence ≥ 0.75
- Normal traffic suppression: bỏ qua traffic bình thường
- Whitelist check: bỏ qua IP trong danh sách trắng
- Cooldown per-IP: Redis TTL keys (fallback in-memory)
- Correlation & severity escalation: tăng severity nếu cùng IP tấn công nhiều lần

**Severity levels:**

| Severity | Điều kiện |
|---|---|
| `critical` | confidence ≥ 0.90, hoặc escalated bởi correlation |
| `high` | confidence ≥ 0.80, hoặc escalated |
| `medium` | confidence ≥ 0.75 |
| `low` | dưới threshold |

**API quản lý alerts:**
- `GET /api/alerts/` — Danh sách alerts (filter theo severity, status, phân trang)
- `GET /api/alerts/{alert_id}` — Chi tiết một alert
- `PUT /api/alerts/{alert_id}/resolve` — Đánh dấu đã xử lý (kèm ghi chú)
- `DELETE /api/alerts/{alert_id}` — Xóa alert

**Dữ liệu lưu trữ:**
- PostgreSQL: `attack_alerts`, `attack_history`, `traffic_flows`, `flow_features`
- MongoDB: `flow_logs` (raw flow summary, fire-and-forget)

---

## 3. Cập nhật thời gian thực (WebSocket)

Kết nối: `ws://localhost:8000/ws` (không yêu cầu authentication)

**Cơ chế hoạt động:**
- `AlertBroadcastBridge`: queue.Queue thread-safe giữa sniffer thread và event loop
- Consumer async loop đọc queue và broadcast đến tất cả WebSocket clients
- Queue size: 10.000 messages, drop với warning nếu đầy

**Message format:**
```json
{
  "type": "alert",
  "data": {
    "alert_id": "uuid",
    "attack_type": "DDoS",
    "severity": "critical",
    "confidence": 0.95,
    "src_ip": "192.168.1.100",
    "dst_ip": "10.0.0.1",
    "timestamp": "2026-05-22T10:00:00",
    "correlated": true
  }
}
```

---

## 4. Giám sát traffic (Traffic Monitoring)

Các endpoint read-only, không yêu cầu API key, không điều khiển sniffer.

- `GET /api/traffic/stats` — Snapshot: số flows active, pipeline state, timestamp
- `GET /api/traffic/flows` — Danh sách flows đang active trong bộ nhớ
- `GET /api/traffic/flows/{src_ip}` — Flows theo source IP
- `GET /api/traffic/top-talkers` — Top IPs theo packet count
- `POST /api/traffic/flows/cleanup` — Xóa flows hết hạn (maintenance)

---

## 5. Quản lý danh sách trắng (Whitelist)

IP trong whitelist sẽ không bao giờ sinh alert, dù ML model phát hiện tấn công.

**Đồng bộ 2 lớp:**
- PostgreSQL: lưu trữ persistent
- AlertManager in-memory set: dùng khi check real-time

**API:**
- `GET /api/whitelist/list` — Danh sách (kèm trạng thái in-memory)
- `POST /api/whitelist/add` — Thêm IP (validate IPv4, port 1-65535, protocol tcp/udp/icmp)
- `POST /api/whitelist/remove` — Xóa theo `whitelist_id` hoặc `ip_address`

---

## 6. Machine Learning Models

**Pipeline model** (dùng cho real-time detection):
- `ModelLoader`: load `ensemble.pkl` + `ensemble_scaler.pkl` + `ensemble_encoder.pkl`
- `Predictor`: validate feature contract, apply scaler, run inference, decode label
- Feature contract: 20 features theo thứ tự cố định trong `models/features.json`

**Attack classes:** Normal, DDoS, PortScan, BruteForce, Botnet, Abnormal

**Legacy model API** (dùng cho manual prediction):
- `GET /api/models/` — Danh sách models trong database
- `POST /api/models/load/{model_id}` — Kích hoạt model theo ID
- `POST /api/predictions/` — Predict từ feature dict
- `POST /api/predictions/batch` — Batch predict

---

## 7. Explainable AI (XAI)

`POST /api/xai/explain` — Giải thích tại sao model đưa ra dự đoán đó.

**Công nghệ:** SHAP TreeExplainer (chỉ hỗ trợ tree-based models: RandomForest, XGBoost)

**Input:** 20 features theo đúng contract  
**Output:**
- `predicted_label`: nhãn dự đoán
- `confidence`: độ tin cậy
- `top_features`: 5 features ảnh hưởng nhất (kèm SHAP value)
- `shap_values`: SHAP value cho tất cả 20 features
- `base_value`: baseline prediction

Rate limit: 60 req/60s per IP.

---

## 8. Email Notifications

Gửi email tự động khi phát hiện tấn công nghiêm trọng.

**Gate conditions** (tất cả phải đúng):
1. `ENABLE_EMAIL_ALERTS=true`
2. `severity` ∈ {`high`, `critical`}
3. `confidence` ≥ 0.85
4. IP chưa trong email cooldown (default: 60 giây)

**Tính năng:**
- Async dispatch (aiosmtplib) — không block pipeline
- Multi-recipient (SMTP_TO comma-separated)
- HTML + plain text email
- Per-IP cooldown riêng biệt với alert cooldown

---

## 9. Bảo mật API

### X-API-Key Authentication
Tất cả `/api/sniffer/*` endpoints yêu cầu header `X-API-Key`.  
Dùng `secrets.compare_digest` để chống timing attack.

### Rate Limiting (Sliding Window)

| Endpoint group | Limit |
|---|---|
| `/api/sniffer/*` | 10 req / 60s per IP |
| `/api/whitelist/*` | 30 req / 60s per IP |
| `/api/xai/*` | 60 req / 60s per IP |

### Input Validation
- IPv4: regex validation, từ chối hostname/IPv6
- Interface name: từ chối shell injection chars (`;`, `|`, `` ` ``, `$`, `/`)
- Port: 1–65535
- Protocol: allowlist (tcp/udp/icmp)

### Production Security
Khi `ENVIRONMENT=production`, backend từ chối khởi động nếu dùng default secrets.

---

## 10. Health Check & Monitoring

### Health Endpoints
- `GET /health` — Basic liveness (pipeline running state)
- `GET /health/detailed` — Connectivity check: PostgreSQL, Redis, MongoDB, model loaded

### Prometheus Metrics
`GET /metrics` — Prometheus text format. Các metrics được định nghĩa trong `monitoring/metrics.py`:
- `http_requests_total`, `http_request_duration_seconds`
- `alerts_total`, `alerts_by_confidence`
- `packets_captured_total`, `flows_processed_total`, `predictions_total`
- `websocket_connections_active`, `websocket_messages_total`
- `emails_sent_total`

### Structured JSON Logging
Tất cả logs ở định dạng JSON (python-json-logger), ghi vào `logs/backend.log` và stdout.

---

## 11. Thống kê hệ thống

- `GET /api/stats/alert-engine` — Thống kê AlertManager: total alerts, by type, by severity, whitelist count
- `GET /api/stats/system` — Thống kê từ database: total/active/resolved alerts, severity distribution

---

## 12. Caching (Redis)

Redis được dùng cho:
- **Alert cooldown**: TTL keys `alert_cooldown:{ip}` — tránh spam alerts cùng IP
- **Optional caching**: `RedisCache` class hỗ trợ get/set/delete với TTL

Nếu Redis không available, hệ thống tự động fallback sang in-memory tracking — pipeline không bị ảnh hưởng.
