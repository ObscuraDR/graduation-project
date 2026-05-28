# IDS Backend API Reference

All endpoints are served by `backend/main.py` unless noted. Base URL example: `http://localhost:8000`.

**OpenAPI:** Interactive docs at `/docs` and `/redoc` when the server is running.

---

## 1. Authentication summary

| Route prefix | `X-API-Key` required |
|--------------|---------------------|
| `/api/sniffer/*` | **Yes** (router-level `Depends(verify_api_key)`) |
| `/api/alerts/*` | No |
| `/api/predictions/*` | No |
| `/api/models/*` | No |
| `/api/whitelist/*` | No |
| `/api/stats/*` | No |
| `/api/traffic/*` | No |
| `/api/xai/*` | No |
| `/health`, `/health/detailed`, `/metrics` | No |
| `/ws` | No |

Header format:

```http
X-API-Key: <value of API_KEY in .env>
```

Implementation: `backend/api/dependencies.py` — `secrets.compare_digest` for timing-safe comparison.  
Missing/invalid key → **401** with `WWW-Authenticate: ApiKey`.

---

## 2. Rate limiting

**Module:** `backend/api/middleware/rate_limit.py`  
**Scope:** Per client IP (honors `X-Forwarded-For` first hop)

| Path prefix | Limit | Window |
|-------------|-------|--------|
| `/api/sniffer/` | 10 requests | 60 seconds |
| `/api/whitelist/` | 30 requests | 60 seconds |
| `/api/xai/` | 60 requests | 60 seconds |

Exceeded → **429**:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Limit: 10 req/60s per IP.",
  "retry_after_seconds": 42
}
```

Header: `Retry-After: <seconds>`

---

## 3. System endpoints

### `GET /health`

**Auth:** None

**Response 200:**

```json
{
  "status": "healthy",
  "service": "IDS Backend",
  "version": "1.0.0",
  "pipeline_running": false
}
```

`pipeline_running` reads `sniffer_routes.pipeline_coordinator.is_running`.

---

### `GET /health/detailed`

**Auth:** None

**Response 200:**

```json
{
  "postgres": { "connected": true },
  "redis": { "connected": true },
  "mongo": { "connected": true },
  "model_loaded": true,
  "pipeline_running": false,
  "timestamp": "2026-05-21T12:00:00+00:00"
}
```

Checks: SQL `SELECT 1`, Redis ping, Mongo `admin.command("ping")`, `get_model_loader().is_loaded`.

---

### `GET /metrics`

**Auth:** None  
**Content-Type:** Prometheus text format (`prometheus_client`)

**Module:** `backend/monitoring/metrics.py`

Note: Counter/histogram helpers exist but are **not instrumented** in request/pipeline code paths today.

---

### `WebSocket /ws`

**Auth:** None  
**Module:** `backend/main.py`, `backend/api/websocket.py`

**Behavior:**

- On connect: `ConnectionManager.connect` accepts socket.
- Server echoes client text: `Received: <message>` (personal message).
- Pipeline alerts: broadcast JSON `{"type":"alert","data":{...}}` via `AlertBroadcastBridge`.

**Disconnect:** handled via `WebSocketDisconnect`.

---

## 4. Sniffer API (`/api/sniffer`)

**Router:** `backend/api/routes/sniffer.py`  
**Auth:** Required on all routes

### `POST /api/sniffer/start`

**Query parameters:**

| Name | Type | Default | Validation |
|------|------|---------|------------|
| `interface` | string | `eth0` | Safe chars + OS exists |
| `filter_expr` | string | `ip` | BPF string passed to Scapy |
| `model_name` | string | `ensemble` | Must load from `models/` |
| `min_packets` | int | 10 | 1–10000 |
| `prediction_mode` | string | `once` | `once` or `window` |
| `prediction_interval_sec` | float | 5.0 | Used in window mode |
| `flow_expire_sec` | int | 30 | |
| `dry_run` | bool | false | 3s capture test |

**Response 200 (success):**

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

**Response 200 (already running):**

```json
{ "status": "error", "message": "Sniffer is already running" }
```

**Errors:**

| Code | Cause |
|------|-------|
| 401 | Missing/invalid API key |
| 422 | Invalid `min_packets` or `prediction_mode` |
| 400 | Interface not found (detail includes `available_interfaces`) |
| 429 | Rate limit |

**Example:**

```bash
curl -X POST "http://localhost:8000/api/sniffer/start?interface=Wi-Fi&dry_run=true" \
  -H "X-API-Key: $API_KEY"
```

---

### `POST /api/sniffer/stop`

**Response 200 (success):**

```json
{ "status": "success", "message": "Sniffer stopped" }
```

**Response 200 (not running):**

```json
{ "status": "error", "message": "Sniffer is not running" }
```

---

### `GET /api/sniffer/status`

**Response 200:** Full stats from `PipelineCoordinator.get_stats()` plus `"status": "running"|"stopped"`.

If never started:

```json
{
  "status": "stopped",
  "message": "Sniffer not initialized",
  "is_running": false
}
```

Includes: `processed_packets`, `inference_runs`, `sniffer_stats`, `flow_builder_stats`, `predictor_stats`, `alert_manager_stats`, etc.

---

## 5. Traffic API (`/api/traffic`)

**Router:** `backend/api/routes/traffic.py`  
**Auth:** None  
**Note:** Does **not** start/stop capture.

### `GET /api/traffic/stats`

```json
{
  "flows": { "active_flows": 0, "total_flows_created": 0, ... },
  "pipeline": { "is_running": false, "message": "Pipeline idle — use POST /api/sniffer/start to begin capture", ... },
  "timestamp": "2026-05-21T12:00:00"
}
```

### `GET /api/traffic/flows?limit=100`

List of active in-memory flows (max `limit`).

### `GET /api/traffic/flows/{src_ip}`

Flows filtered by source IP.

### `GET /api/traffic/top-talkers?limit=10`

Aggregated packet/byte counts per source IP.

### `POST /api/traffic/flows/cleanup`

Removes expired flows via `FlowBuilder.cleanup_expired_flows()`.

```json
{
  "message": "Expired flows cleaned up",
  "expired_count": 3,
  "active_flows": 12
}
```

---

## 6. Alerts API (`/api/alerts`)

**Router:** `backend/api/legacy_routes.py` — `alerts_router`

### `GET /api/alerts/`

**Query:** `skip`, `limit`, `severity`, `status` (alias for alert status)

**Response:** Array of alert objects from PostgreSQL.

### `GET /api/alerts/{alert_id}`

**404** if not found.

### `PUT /api/alerts/{alert_id}/resolve?notes=optional`

Sets `status=resolved`, `is_resolved=true`, `resolved_at=now`.

### `DELETE /api/alerts/{alert_id}`

Deletes row from `attack_alerts`.

---

## 7. Predictions API (`/api/predictions`)

**Router:** `legacy_routes.py` — uses global `ml_model` (`IDSModel` from `backend/ml/models.py`)

**Not** the same code path as live pipeline `Predictor`.

### `POST /api/predictions/`

**Body:** JSON object of feature key-values (legacy schema; not enforced against `features.json`).

**503** if `ml_model` not loaded:

```json
{ "detail": "ML model not loaded or not trained" }
```

**Response 200:**

```json
{
  "class": "DDoS",
  "confidence": 0.91,
  "model_name": "ensemble",
  "model_version": "1.0",
  "all_probabilities": { "Normal": 0.09, "DDoS": 0.91 }
}
```

### `POST /api/predictions/batch`

**Body:** JSON array of feature objects.

**Response:**

```json
{ "predictions": [ { "class": "...", "confidence": 0.9, ... } ] }
```

---

## 8. Models API (`/api/models`)

### `GET /api/models/`

Lists rows from PostgreSQL `models` table.

### `POST /api/models/load/{model_id}`

Loads `RandomForestIDS` or `XGBoostIDS` from `file_path` into global `ml_model`.  
Supported algorithms: `RandomForest`, `XGBoost` only.

**404** unknown id. **500** load failure.

---

## 9. Whitelist API (`/api/whitelist`)

**Envelope:** `ApiResponse` — `{ "success": bool, "message": str, "data": object|null }`

### `GET /api/whitelist/list`

Returns DB entries plus `in_memory_ips` from `AlertManager`.

### `POST /api/whitelist/add`

**Body:**

```json
{
  "ip_address": "192.168.1.10",
  "port": null,
  "protocol": null,
  "reason": "Trusted scanner"
}
```

**201** on success. **409** if IP already exists.

### `POST /api/whitelist/remove`

**Body:** `{ "whitelist_id": 1 }` or `{ "ip_address": "192.168.1.10" }`

**404** if not found.

### Legacy (hidden from OpenAPI schema)

- `GET /api/whitelist/` → same as list
- `DELETE /api/whitelist/{whitelist_id}` → remove by id

---

## 10. Statistics API (`/api/stats`)

### `GET /api/stats/alert-engine`

In-memory stats from `alert_manager.get_stats()`.

### `GET /api/stats/system`

PostgreSQL counts: alerts by severity, whitelist count, model count.

---

## 11. XAI API (`/api/xai`)

**Router:** `backend/api/routes/xai.py`

### `POST /api/xai/explain`

**Body:**

```json
{
  "model_name": "ensemble",
  "features": {
    "flow_duration": 1.5,
    "total_fwd_packets": 10,
    "total_bwd_packets": 2,
    "total_fwd_bytes": 1200,
    "total_bwd_bytes": 400,
    "avg_packet_size": 120.0,
    "packet_rate": 50.0,
    "byte_rate": 6000.0,
    "syn_count": 1,
    "fin_count": 0,
    "rst_count": 0,
    "psh_count": 2,
    "ack_count": 8,
    "unique_dst_ports": 1,
    "inter_arrival_time_mean": 0.02,
    "fwd_packet_rate": 40.0,
    "bwd_packet_rate": 10.0,
    "fwd_byte_rate": 5000.0,
    "bwd_byte_rate": 1000.0,
    "packet_length_mean": 115.0
  }
}
```

All **20** keys from `models/features.json` are required.

**Response 200:**

```json
{
  "success": true,
  "message": "Explanation generated",
  "data": {
    "model_name": "ensemble",
    "predicted_label": "DDoS",
    "confidence": 0.91,
    "probabilities": { "Normal": 0.09, "DDoS": 0.91 },
    "base_value": 0.12,
    "top_features": [
      { "feature": "packet_rate", "value": 50.0, "shap_value": 0.34 }
    ],
    "shap_values": { "flow_duration": -0.02 }
  }
}
```

**Errors:**

| Code | `detail.error` |
|------|----------------|
| 422 | `FeatureContractError` — missing/extra features |
| 400 | `UnsupportedModelError` — non-tree model |
| 500 | `ModelLoadError` or `InternalError` |

---

## 12. Common HTTP status codes

| Code | When |
|------|------|
| 200 | Success |
| 201 | Whitelist add |
| 401 | Invalid API key (sniffer only) |
| 404 | Resource not found |
| 409 | Whitelist duplicate |
| 422 | Validation (Pydantic, interface, XAI features) |
| 429 | Rate limit |
| 500 | Server/prediction/model errors |
| 503 | Legacy ML model not loaded |

---

## 13. Production configuration errors

If `ENVIRONMENT=production` and secrets/CORS are invalid, the **process exits at import** before binding port — no HTTP response.

---

## 14. Verification

```bash
# Sniffer (requires API_KEY)
export API_KEY=changeme-set-API_KEY-in-env
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/api/sniffer/status | jq

# Alerts (no key)
curl -s http://localhost:8000/api/alerts/?limit=5 | jq

# OpenAPI
curl -s http://localhost:8000/openapi.json | jq '.paths | keys'
```

Automated tests: `backend/tests/test_api_security.py`, `test_rate_limiting.py`, `test_websocket_broadcast.py`.
