# Z-Sentinel IDS — API Documentation

## Base URL
```
http://localhost:8000
```

## Authentication

Các endpoint nhạy cảm yêu cầu header `X-API-Key`:
```
X-API-Key: <your-api-key>
```
Giá trị lấy từ biến môi trường `API_KEY` trong `.env`.

Endpoint **không** yêu cầu auth: `/health`, `/health/detailed`, `/metrics`, `/ws`, `/api/traffic/*`, `/api/alerts/*`, `/api/stats/*`.

---

## Health

### Basic Health Check
```http
GET /health
```
**Response:**
```json
{
  "status": "healthy",
  "service": "IDS Backend",
  "version": "1.0.0",
  "pipeline_running": false
}
```

### Detailed Health Check
```http
GET /health/detailed
```
Kiểm tra kết nối tất cả backing services.

**Response:**
```json
{
  "postgres": {"connected": true},
  "redis":    {"connected": true},
  "mongo":    {"connected": true},
  "model_loaded": true,
  "pipeline_running": false,
  "timestamp": "2026-05-22T10:00:00.000000+00:00"
}
```

### Prometheus Metrics
```http
GET /metrics
```
Trả về metrics ở định dạng Prometheus text format.

---

## Sniffer — IDS Pipeline Control

> Tất cả endpoints dưới đây yêu cầu `X-API-Key` header.

### Start Pipeline
```http
POST /api/sniffer/start
```

**Query Parameters:**

| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `interface` | string | `eth0` | Tên network interface (ví dụ: `eth0`, `Wi-Fi`) |
| `filter_expr` | string | `ip` | BPF filter expression |
| `model_name` | string | `ensemble` | Tên model artifact trong `models/` |
| `min_packets` | int | `10` | Số packet tối thiểu để trigger inference (1–10000) |
| `prediction_mode` | string | `once` | `once` (1 lần/flow) hoặc `window` (lặp lại theo interval) |
| `prediction_interval_sec` | float | `5.0` | Interval giữa các lần predict (chỉ dùng với `window` mode) |
| `flow_expire_sec` | int | `30` | Thời gian inactive trước khi flow bị xóa |
| `dry_run` | bool | `false` | Nếu `true`, capture 3 giây rồi tự dừng (dùng để test) |

**Response (success):**
```json
{
  "status": "success",
  "message": "Sniffer started on interface eth0",
  "interface": "eth0",
  "filter": "ip",
  "model": "ensemble",
  "min_packets": 10,
  "prediction_mode": "once",
  "prediction_interval_sec": 5.0,
  "flow_expire_sec": 30,
  "dry_run": false
}
```

**Response (already running):**
```json
{"status": "error", "message": "Sniffer is already running"}
```

**Error responses:**
- `401` — Missing/invalid API key
- `400` — Interface not found on host
- `422` — Invalid interface name (injection chars), invalid `min_packets`, invalid `prediction_mode`
- `429` — Rate limit exceeded (10 req/60s per IP)

### Stop Pipeline
```http
POST /api/sniffer/stop
```
**Response:**
```json
{"status": "success", "message": "Sniffer stopped"}
```

### Pipeline Status
```http
GET /api/sniffer/status
```
**Response:**
```json
{
  "status": "running",
  "is_running": true,
  "interface": "eth0",
  "filter_expr": "ip",
  "model_name": "ensemble",
  "min_packets": 10,
  "prediction_mode": "once",
  "processed_packets": 15420,
  "inference_runs": 87,
  "skipped_already_processed": 1203,
  "skipped_below_min_packets": 4230,
  "cleanup_runs": 12,
  "sniffer_stats": {
    "is_running": true,
    "packets_captured": 15420,
    "packets_per_second": 142.3
  },
  "flow_builder_stats": {
    "active_flows": 23,
    "total_flows_created": 156
  },
  "predictor_stats": {
    "total_predictions": 87,
    "attack_predictions": 12,
    "attack_rate": 0.138
  },
  "alert_manager_stats": {
    "total_alerts": 8,
    "alerts_by_type": {"DDoS": 5, "PortScan": 3},
    "alerts_by_severity": {"critical": 3, "high": 5}
  }
}
```

---

## Traffic — Monitoring (Read-only)

> Không yêu cầu API key. Không điều khiển sniffer.

### Traffic Stats
```http
GET /api/traffic/stats
```
**Response:**
```json
{
  "flows": {
    "active_flows": 23,
    "total_flows_created": 156,
    "total_flows_expired": 133
  },
  "pipeline": {
    "is_running": true,
    "processed_packets": 15420
  },
  "timestamp": "2026-05-22T10:00:00.000000"
}
```

### Active Flows
```http
GET /api/traffic/flows?limit=100
```
**Response:**
```json
[
  {
    "flow_key": "192.168.1.5:54321:10.0.0.1:80:tcp",
    "src_ip": "192.168.1.5",
    "dst_ip": "10.0.0.1",
    "src_port": 54321,
    "dst_port": 80,
    "protocol": "tcp",
    "packet_count": 45,
    "byte_count": 6750,
    "flow_duration": 2.34,
    "start_time": "2026-05-22T10:00:00",
    "last_seen": "2026-05-22T10:00:02"
  }
]
```

### Flows by Source IP
```http
GET /api/traffic/flows/{src_ip}
```

### Top Talkers
```http
GET /api/traffic/top-talkers?limit=10
```
**Response:**
```json
[
  {
    "src_ip": "192.168.1.5",
    "packet_count": 15420,
    "byte_count": 2313000,
    "flow_count": 23
  }
]
```

### Cleanup Expired Flows
```http
POST /api/traffic/flows/cleanup
```
Xóa các flow đã hết hạn khỏi bộ nhớ (maintenance endpoint).

---

## Alerts

### Get All Alerts
```http
GET /api/alerts/
```

**Query Parameters:**

| Tham số | Kiểu | Mô tả |
|---|---|---|
| `skip` | int | Số records bỏ qua (default: 0) |
| `limit` | int | Số records trả về (default: 100) |
| `severity` | string | Lọc: `critical`, `high`, `medium`, `low` |
| `status` | string | Lọc: `active`, `resolved`, `ignored` |

**Response:**
```json
[
  {
    "id": 1,
    "alert_id": "550e8400-e29b-41d4-a716-446655440000",
    "source_ip": "192.168.1.100",
    "dest_ip": "10.0.0.1",
    "source_port": 54321,
    "dest_port": 80,
    "attack_type": "DDoS",
    "severity": "critical",
    "confidence": 0.95,
    "timestamp": "2026-05-22T10:00:00",
    "status": "active",
    "is_resolved": false,
    "resolved_at": null,
    "notes": null,
    "model_name": "ensemble",
    "model_version": "1.0"
  }
]
```

### Get Alert by ID
```http
GET /api/alerts/{alert_id}
```
`alert_id` là UUID string (không phải integer id).

**Error:** `404` nếu không tìm thấy.

### Resolve Alert
```http
PUT /api/alerts/{alert_id}/resolve
```
**Query Parameters:** `notes` (string, optional)

**Response:**
```json
{"message": "AttackAlert resolved successfully", "alert_id": "550e8400-..."}
```

### Delete Alert
```http
DELETE /api/alerts/{alert_id}
```

---

## Predictions (Legacy)

> Các endpoint này dùng `IDSModel` từ `backend/ml/models.py` (legacy path). Pipeline thời gian thực dùng `Predictor` + `ModelLoader` trực tiếp.

### Single Prediction
```http
POST /api/predictions/
```
**Body:** Feature dict (key-value pairs)

**Response:**
```json
{
  "class": "DDoS",
  "confidence": 0.95,
  "model_name": "ensemble",
  "model_version": "1.0",
  "all_probabilities": {
    "Normal": 0.05,
    "DDoS": 0.95,
    "PortScan": 0.00
  }
}
```

**Error:** `503` nếu model chưa được load.

### Batch Prediction
```http
POST /api/predictions/batch
```
**Body:** Array of feature dicts

---

## Models

### Get All Models
```http
GET /api/models/
```
**Response:**
```json
[
  {
    "id": 1,
    "model_name": "Ensemble IDS",
    "version": "1.0",
    "algorithm": "RandomForest",
    "accuracy": 0.97,
    "precision": 0.96,
    "recall": 0.95,
    "f1_score": 0.95,
    "is_active": true,
    "created_at": "2026-05-22T10:00:00"
  }
]
```

### Load Model
```http
POST /api/models/load/{model_id}
```
Kích hoạt model theo `model_id` từ database.

---

## Whitelist

### List Whitelist
```http
GET /api/whitelist/list
```
**Response:**
```json
{
  "success": true,
  "message": "Retrieved 2 whitelist entries",
  "data": {
    "items": [
      {
        "id": 1,
        "ip_address": "192.168.1.100",
        "port": null,
        "protocol": null,
        "reason": "Internal server",
        "created_at": "2026-05-22T10:00:00",
        "in_memory": true
      }
    ],
    "total": 2,
    "in_memory_ips": ["192.168.1.100", "10.0.0.5"]
  }
}
```

`in_memory: true` nghĩa là IP đang active trong AlertManager (sẽ được bỏ qua khi phát hiện tấn công).

### Add to Whitelist
```http
POST /api/whitelist/add
```
**Body:**
```json
{
  "ip_address": "192.168.1.100",
  "port": 80,
  "protocol": "tcp",
  "reason": "Internal web server"
}
```

**Validation:**
- `ip_address`: IPv4 hợp lệ (dotted-decimal)
- `port`: 1–65535 (optional)
- `protocol`: `tcp`, `udp`, hoặc `icmp` (optional)

**Response:** `201 Created` với entry data.  
**Error:** `409 Conflict` nếu IP đã tồn tại.

### Remove from Whitelist
```http
POST /api/whitelist/remove
```
**Body** (một trong hai):
```json
{"whitelist_id": 1}
```
hoặc:
```json
{"ip_address": "192.168.1.100"}
```

---

## Statistics

### Alert Engine Stats
```http
GET /api/stats/alert-engine
```
**Response:**
```json
{
  "total_alerts": 42,
  "alerts_by_type": {"DDoS": 20, "PortScan": 15, "BruteForce": 7},
  "alerts_by_severity": {"critical": 10, "high": 20, "medium": 12},
  "whitelist_count": 3,
  "active_attackers": 5,
  "confidence_threshold": 0.75,
  "alert_cooldown": 30,
  "correlation_window": 60
}
```

### System Stats
```http
GET /api/stats/system
```
**Response:**
```json
{
  "total_alerts": 42,
  "active_alerts": 30,
  "resolved_alerts": 12,
  "alerts_by_severity": {
    "critical": 10,
    "high": 20,
    "medium": 8,
    "low": 4
  },
  "whitelist_count": 3,
  "model_count": 1
}
```

---

## XAI — Explainable AI

### Explain Prediction (SHAP)
```http
POST /api/xai/explain
```

> Rate limit: 60 req/60s per IP.

**Body:**
```json
{
  "model_name": "ensemble",
  "features": {
    "flow_duration": 1.5,
    "total_fwd_packets": 500,
    "total_bwd_packets": 10,
    "total_fwd_bytes": 50000,
    "total_bwd_bytes": 1000,
    "avg_packet_size": 100.0,
    "packet_rate": 1200.0,
    "byte_rate": 98000.0,
    "syn_count": 450,
    "fin_count": 2,
    "rst_count": 5,
    "psh_count": 10,
    "ack_count": 50,
    "unique_dst_ports": 1,
    "inter_arrival_time_mean": 0.001,
    "fwd_packet_rate": 1100.0,
    "bwd_packet_rate": 100.0,
    "fwd_byte_rate": 90000.0,
    "bwd_byte_rate": 8000.0,
    "packet_length_mean": 100.0
  }
}
```

**Response (success):**
```json
{
  "success": true,
  "message": "Explanation generated",
  "data": {
    "model_name": "ensemble",
    "predicted_label": "DDoS",
    "confidence": 0.91,
    "probabilities": {"Normal": 0.09, "DDoS": 0.91},
    "base_value": 0.12,
    "top_features": [
      {"feature": "packet_rate", "value": 1200.0, "shap_value": 0.34},
      {"feature": "syn_count",   "value": 450.0,  "shap_value": 0.28},
      {"feature": "fwd_packet_rate", "value": 1100.0, "shap_value": 0.21},
      {"feature": "byte_rate",   "value": 98000.0, "shap_value": 0.15},
      {"feature": "flow_duration", "value": 1.5,  "shap_value": -0.08}
    ],
    "shap_values": {
      "flow_duration": -0.08,
      "packet_rate": 0.34,
      "..."
    }
  }
}
```

**Errors:**
- `422` — Feature keys không khớp với `models/features.json`
- `400` — Model không hỗ trợ SHAP TreeExplainer (chỉ tree-based models)
- `500` — Model file không tìm thấy

---

## WebSocket

### Real-time Alert Stream
```
ws://localhost:8000/ws
```

Không yêu cầu authentication. Nhận tất cả alerts được broadcast.

**Message format:**
```json
{
  "type": "alert",
  "data": {
    "alert_id": "550e8400-e29b-41d4-a716-446655440000",
    "src_ip": "192.168.1.100",
    "dst_ip": "10.0.0.1",
    "src_port": 54321,
    "dst_port": 80,
    "protocol": "tcp",
    "attack_type": "DDoS",
    "confidence": 0.95,
    "severity": "critical",
    "timestamp": "2026-05-22T10:00:00",
    "correlated": true,
    "original_severity": "high",
    "model_name": "ensemble"
  }
}
```

**Gửi message từ client:**
```json
"ping"
```
**Server trả về:**
```json
"Received: ping"
```

---

## Rate Limiting

| Endpoint group | Limit |
|---|---|
| `/api/sniffer/*` | 10 req / 60s per IP |
| `/api/whitelist/*` | 30 req / 60s per IP |
| `/api/xai/*` | 60 req / 60s per IP |
| Tất cả routes khác | Không giới hạn |

**HTTP 429 Response:**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Limit: 10 req/60s per IP.",
  "retry_after_seconds": 42
}
```
Header: `Retry-After: 42`

---

## Input Validation

| Field | Rule | HTTP Error |
|---|---|---|
| `ip_address` | IPv4 dotted-decimal hợp lệ | 422 |
| `port` | Integer 1–65535 | 422 |
| `protocol` | `tcp`, `udp`, hoặc `icmp` | 422 |
| `interface` | Alphanumeric + space/hyphen/underscore/dot, ≤ 64 chars | 422 |
| `min_packets` | Integer 1–10000 | 422 |
| `prediction_mode` | `once` hoặc `window` | 422 |

---

## Error Responses

```json
{"detail": "Error message"}
```

| Status | Ý nghĩa |
|---|---|
| 400 | Bad Request (interface not found, etc.) |
| 401 | Unauthorized (missing/invalid API key) |
| 404 | Not Found |
| 409 | Conflict (duplicate whitelist entry) |
| 422 | Unprocessable Entity (validation error) |
| 429 | Too Many Requests (rate limit) |
| 500 | Internal Server Error |
| 503 | Service Unavailable (model not loaded) |
