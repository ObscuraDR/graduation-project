# IDS Real-Time Pipeline Flow

End-to-end documentation of the **live IDS pipeline** as implemented in `backend/pipeline/coordinator.py` and its dependencies. Offline training is covered in `docs/ML_PIPELINE.md`.

---

## 1. Pipeline activation

The pipeline is **not** started at application boot. It starts only when an authenticated client calls:

```
POST /api/sniffer/start
Header: X-API-Key: <API_KEY from .env>
```

Implementation: `backend/api/routes/sniffer.py`

| Parameter | Default | Source |
|-----------|---------|--------|
| `interface` | `eth0` | Query |
| `filter_expr` | `ip` | Query (BPF) |
| `model_name` | `ensemble` | Query → `ModelLoader.load_from_directory` |
| `min_packets` | `10` | Query → `settings.min_packets` |
| `prediction_mode` | `once` | `once` \| `window` |
| `prediction_interval_sec` | `5.0` | Window mode only |
| `flow_expire_sec` | `30` | FlowBuilder |
| `dry_run` | `false` | Sniffer captures ~3s then stops |

Stop: `POST /api/sniffer/stop`  
Status: `GET /api/sniffer/status`

---

## 2. High-level sequence diagram

```
Client                FastAPI              Coordinator           Sniffer Thread
  │                      │                      │                      │
  │ POST /sniffer/start  │                      │                      │
  ├─────────────────────►│                      │                      │
  │                      │ create_task(start)   │                      │
  │                      ├─────────────────────►│ initialize()         │
  │                      │                      │ sniffer.start()      │
  │                      │                      ├─────────────────────►│ sniff loop
  │                      │                      │                      │
  │                      │                      │◄── packet_callback ──┤
  │                      │                      │  (per packet)        │
  │                      │                      │                      │
  │ WS /ws               │                      │                      │
  │◄─────────────────────┼── bridge.broadcast ──┤ (if attack)          │
```

---

## 3. Packet capture lifecycle

**Module:** `backend/capture_engine/packet_sniffer.py`  
**Class:** `PacketSniffer`

### 3.1 Start

```python
# coordinator.start() after initialize()
self.sniffer.callback = self.packet_callback
self.sniffer.start()  # daemon thread → _run_sniffer()
```

`_run_sniffer()` calls Scapy:

```python
sniff(iface=self.interface, prn=self._packet_handler, filter=self.filter_expr, store=False)
```

Dry run adds `timeout=self.dry_run_duration` (default 3.0s) and sets `is_running = False` when complete.

### 3.2 Per-packet handler

`_packet_handler(packet)`:

1. `_extract_packet_info(packet)` → dict with `timestamp`, `length`, `src_ip`, `dst_ip`, ports, `protocol`, `tcp_flags`, `payload_size`.
2. Enqueue to internal `queue.Queue` (max 10,000) if not full.
3. Invoke `callback(packet_info)` if set — **this is the pipeline entry**.
4. Increment `packets_captured`; log rate every 1000 packets.

### 3.3 Stop

`coordinator.stop()` → `sniffer.stop()` → `join` thread (5s timeout). Scapy `sniff` may not exit instantly on all platforms.

### 3.4 Interface validation (before start)

1. `require_valid_interface(interface)` — regex safety (`api/validation.py`).
2. `validate_interface(interface)` — OS interface list via Scapy (`get_if_list` / Windows `get_windows_if_list`).

---

## 4. FlowBuilder lifecycle

**Module:** `backend/flow_engine/flow_builder.py`  
**Classes:** `Flow`, `FlowBuilder`

### 4.1 Flow key (5-tuple)

```
{src_ip}:{src_port}:{dst_ip}:{dst_port}:{protocol}
```

Packets missing `src_ip` or `dst_ip` are dropped with a warning.

### 4.2 Flow state updates

Each packet calls `flow.add_packet(packet_info)`:

- Counters: `packet_count`, `byte_count`, forward/backward packets and bytes
- TCP flag counts (SYN, FIN, RST, PSH, ACK)
- `unique_dst_ports` set
- Inter-arrival times between packets

### 4.3 Inference gating

Before ML runs, `PipelineCoordinator._should_skip_inference(flow)` checks:

| Check | Behavior |
|-------|----------|
| `packet_count < min_packets_per_flow` | Skip; increment `skipped_below_min_packets` |
| `flow.should_run_inference(...)` false | Skip; increment `skipped_already_processed` |

**`once` mode** (`Flow.should_run_inference`):

- Run inference when `packet_count >= min_packets` and `processed == False`.

**`window` mode**:

- First run when thresholds met.
- Subsequent runs only if `elapsed >= prediction_interval_sec` since `last_predicted_at`.

After successful inference: `flow.mark_inference_complete()` sets `processed=True`, updates `last_predicted_at`, increments `prediction_count`.

### 4.4 Flow expiry (memory management)

`flow_builder.cleanup_expired_flows()` removes flows when:

| Rule | Setting default |
|------|-----------------|
| Inactive longer than `flow_expire_sec` | 30s |
| Age exceeds `flow_max_lifetime_sec` | 60s |
| Processed and past `processed_flow_retention_sec` since last prediction | 45s |

Triggered every 500 packets (when inference skipped) and every 50 inference runs.

---

## 5. Feature extraction

**Module:** `backend/feature_engine/feature_extractor.py`

On inference due:

```python
features = self.feature_extractor.extract_features(flow)
```

Produces **20 features** (order defined in `get_feature_names()`), aligned with `models/features.json`.

The coordinator also calls `predictor.predict_flow(flow)` which extracts features again internally — duplicate extraction per inference cycle.

---

## 6. ML prediction

**Modules:** `backend/detection_engine/predictor.py`, `model_loader.py`

### 6.1 Model load (pipeline initialize)

```python
model_loader = get_model_loader()
model_loader.load_from_directory(self.model_name)
# Loads: models/{model_name}.pkl
#         models/{model_name}_scaler.pkl
#         models/{model_name}_encoder.pkl
```

Failure → `RuntimeError("Model not found: ...")` aborts pipeline start.

### 6.2 predict_flow

1. `feature_extractor.extract_features(flow)`
2. `_validate_features` — order from `features.json`; NaN→0, inf clamped
3. `model_loader.predict` / `predict_proba`
4. Map class index → `attack_type` via label encoder
5. `confidence = max(probabilities)`
6. `_determine_severity(confidence, attack_type)`:
   - Normal → `low`
   - confidence ≥ 0.9 → `critical`
   - ≥ 0.8 → `high`
   - ≥ `confidence_threshold` (default 0.75) → `medium`
   - else → `low`

### 6.3 Attack decision

```python
predictor.is_attack(prediction):
    attack_type != "Normal" and confidence >= confidence_threshold
```

Only then does the pipeline persist and alert.

---

## 7. Alert generation

**Module:** `backend/alert_engine/alert_manager.py`

`alert_manager.generate_alert(prediction, flow.get_stats(), flow_id=...)`

### 7.1 Suppression gates

| Gate | Condition |
|------|-----------|
| Normal traffic | `attack_type == "Normal"` |
| Low confidence | `confidence < confidence_threshold` (default 0.75) |
| Missing src IP | `flow_info` lacks `src_ip` |
| Whitelist | IP in `alert_manager.whitelist` (in-memory set) |
| Cooldown | Redis key `alert_cooldown:{ip}` or in-memory `alert_history` |

### 7.2 Correlation (severity adjustment)

`correlation_window` default **60 seconds**. Recent alerts per `src_ip` in `attack_patterns`:

| Pattern | Effect |
|---------|--------|
| ≥ 5 recent attacks | Bump low/medium → high; high → critical |
| ≥ 3 PortScan / Port Sweep | → critical |
| ≥ 2 DDoS | → critical |

Sets `correlated: true` when severity changes.

### 7.3 Side effects (on accepted alert)

1. **PostgreSQL** — `AttackAlertRepository.create_alert`, `AttackHistoryRepository.update_or_create_history`
2. **WebSocket** — `broadcast_bridge.enqueue_alert(alert)` (non-blocking)
3. **Email** — `email_service.dispatch_alert_email(alert)` (see architecture note on thread/event loop)

---

## 8. Database persistence (attack path only)

**Module:** `backend/pipeline/coordinator.py` — `_save_flow_to_db`

When `predictor.is_attack(prediction)`:

```
SessionLocal()
  → TrafficFlowRepository.create_flow(db, flow_data)
  → FlowFeatureRepository.create_feature(db, features, traffic_flow.id)
  → return traffic_flow.id
```

**MongoDB** — `log_flow_summary(flow_id, flow.get_stats(), features)` in `mongo_logger.py`:

- Collection: `flow_logs`
- Failures logged as warnings; **do not block** pipeline

---

## 9. WebSocket broadcast

**Module:** `backend/api/websocket.py`

### 9.1 Enqueue (sniffer thread)

```python
message = {"type": "alert", "data": alert}
broadcast_bridge.enqueue_alert(alert)  # put_nowait on Queue(maxsize=10000)
```

Queue full → alert dropped; `dropped_total` incremented.

### 9.2 Consume (asyncio)

`AlertBroadcastBridge.start()` runs `_consume_loop`:

- `await asyncio.to_thread(self._blocking_get, 0.25)` 
- `await ConnectionManager.broadcast(message)`

### 9.3 Client wire format

```json
{
  "type": "alert",
  "data": {
    "alert_id": "uuid",
    "src_ip": "...",
    "attack_type": "...",
    "severity": "...",
    "confidence": 0.92,
    "timestamp": "...",
    ...
  }
}
```

WebSocket endpoint: `GET /ws` upgrade in `main.py` — **no API key**.

---

## 10. Coordinator main loop

After `sniffer.start()`:

```python
while self.is_running:
    await asyncio.sleep(1)
```

The asyncio task stays alive until `stop()` sets `is_running = False` and cancels the task from the sniffer route.

---

## 11. Standalone CLI path (`run_sniffer.py`)

Same logical stages without:

- FastAPI / WebSocket bridge
- PostgreSQL / Mongo persistence (alerts may still hit DB if `enable_db_save` on AlertManager)
- Inference gating uses hardcoded `flow.packet_count >= 10` only (no once/window)

---

## 12. Configuration knobs (pipeline)

From `backend/config.py` / `.env`:

| Variable | Default | Effect |
|----------|---------|--------|
| `MIN_PACKETS` | 10 | Min packets before inference |
| `PREDICTION_MODE` | once | once \| window |
| `PREDICTION_INTERVAL_SEC` | 5.0 | Window re-inference interval |
| `FLOW_EXPIRE_SEC` | 30 | Inactive flow removal |
| `FLOW_MAX_LIFETIME_SEC` | 60 | Max flow age |
| `PROCESSED_FLOW_RETENTION_SEC` | 45 | Post-inference retention |

Alert manager defaults (constructor): `confidence_threshold=0.75`, `alert_cooldown=30`, `correlation_window=60`.

---

## 13. Verification

```bash
# Start pipeline (replace key and interface)
curl -X POST "http://localhost:8000/api/sniffer/start?interface=eth0&dry_run=true" \
  -H "X-API-Key: changeme-set-API_KEY-in-env"

# Status
curl -H "X-API-Key: changeme-set-API_KEY-in-env" \
  http://localhost:8000/api/sniffer/status

# Traffic snapshot (no auth)
curl http://localhost:8000/api/traffic/stats

# WebSocket (wscat example)
wscat -c ws://localhost:8000/ws
```

---

## 14. Known limitations

1. Scapy `sniff` blocking stop — thread join may timeout.
2. Duplicate feature extraction per inference in coordinator.
3. Email dispatch from sniffer thread may not schedule asyncio tasks reliably.
4. `get_flow_builder()` singleton — parameters updated on coordinator reuse but flows dict persists across stops unless cleaned.
5. Dry run sets sniffer `is_running=False` in thread; coordinator loop may still run until explicit stop.
6. `privileged: true` still present in docker-compose.yml — should use only `NET_RAW` + `NET_ADMIN` capabilities.

See `docs/TROUBLESHOOTING.md` for operational fixes.
