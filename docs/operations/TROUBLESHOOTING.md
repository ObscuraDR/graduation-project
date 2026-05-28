# Troubleshooting Guide

Operational symptoms, causes, and fixes grounded in the current codebase. Commands assume project root and `.env` configured.

---

## 1. Application fails to start

### Symptom: Process exits immediately with production error

```
[PRODUCTION] Startup blocked — insecure configuration
```

**Cause:** `ENVIRONMENT=production` and weak `SECRET_KEY`, `API_KEY`, or missing `CORS_ORIGINS`.

**Fix:**

```bash
export ENVIRONMENT=production
export SECRET_KEY=$(openssl rand -hex 32)
export API_KEY=$(openssl rand -hex 16)
export CORS_ORIGINS=https://your-dashboard.example.com
python backend/scripts/verify_config_security.py
```

---

### Symptom: `[PRODUCTION] CORS_ORIGINS is empty — refusing to start`

**Cause:** `main.py` exits when `settings.cors_origins` is empty (production has no dev defaults).

**Fix:** Set `CORS_ORIGINS` in `.env`.

---

### Symptom: `RuntimeError` on `get_settings()` at import

**Cause:** Same as production validator.

**Fix:** Use `ENVIRONMENT=development` for local dev or fix secrets.

---

## 2. Missing model artifacts

### Symptom: Sniffer start fails / logs `Model not found: ensemble`

**Cause:** `PipelineCoordinator.initialize()` — `model_loader.load_from_directory()` returns False when files missing under `models/`.

**Expected files:**

```
models/ensemble.pkl
models/ensemble_scaler.pkl
models/ensemble_encoder.pkl
```

**Fix:**

```bash
python backend/ml/create_dummy_models.py
# or train:
python backend/ml/train_flow_model.py --data-path data/cicids2017/processed.csv
ls -la models/
```

**Verify:**

```bash
python backend/scripts/verify_real_model.py
curl http://localhost:8000/health/detailed
# model_loaded: false until first successful load
```

---

### Symptom: `FeatureContractError` at predictor init

**Cause:** `models/features.json` out of sync with `feature_extractor.py`.

**Fix:**

```bash
python backend/scripts/validate_features.py
```

Regenerate `features.json` from training pipeline if needed.

---

## 3. PostgreSQL failures

### Symptom: `Error initializing database` in logs on startup

**Cause:** `init_db()` cannot reach Postgres or auth failed.

**Fix:**

```bash
# Check connection env
echo $POSTGRES_HOST $POSTGRES_PORT $POSTGRES_DB

# Docker
docker compose ps postgres
docker compose logs postgres

# Manual test
python -c "from backend.database.connection import engine; engine.connect()"
```

**Note:** Startup **continues** even if init logs error — tables may be missing.

---

### Symptom: Alert APIs return 500 / SQL errors

**Cause:** Tables not created.

**Fix:**

```bash
# Option 1: Alembic (recommended)
alembic upgrade head

# Option 2: Legacy init script
python backend/database/init_db.py
```

---

### Symptom: Seed script fails on whitelist

**Cause:** Typo in `backend/database/init_db.py` line 52: `Whititelist` instead of `Whitelist`.

**Fix:** Correct typo in code (or insert whitelist rows manually via SQL/API).

---

## 4. Redis failures

### Symptom: `health/detailed` shows `"redis": {"connected": false}`

**Cause:** Redis down, wrong password, or `REDIS_URL` mismatch.

**Fix:**

```bash
python backend/scripts/test_redis_connection.py

# Docker compose password
REDIS_URL=redis://:ids_redis_pass@localhost:6379/0
```

**Behavior:** System **degrades gracefully** — alert cooldown uses in-memory dict in `AlertManager` only for that process.

---

## 5. MongoDB failures

### Symptom: `MongoDB flow log skipped` warnings

**Cause:** Mongo unreachable or auth failure in `log_flow_summary`.

**Fix:**

```bash
python backend/scripts/test_mongo_connection.py
# Docker:
MONGO_URI=mongodb://ids_mongo_user:ids_mongo_pass@localhost:27017/ids_logs?authSource=admin
```

**Impact:** Pipeline continues; no `flow_logs` documents.

---

## 6. Sniffer / packet capture issues

### Symptom: HTTP 400 with `available_interfaces` list

**Cause:** Invalid `interface` query param for host.

**Fix:**

```bash
python backend/scripts/list_interfaces.py
curl -X POST "http://localhost:8000/api/sniffer/start?interface=<NAME>" -H "X-API-Key: $API_KEY"
```

Use exact name from list (`eth0`, `Wi-Fi`, etc.).

---

### Symptom: HTTP 422 on start

**Cause:** Invalid `min_packets` or `prediction_mode`.

**Fix:** Use `min_packets` 1–10000 and `prediction_mode` `once` or `window`.

---

### Symptom: `Npcap is required on Windows`

**Cause:** Scapy cannot access adapter without Npcap.

**Fix:** Install Npcap (WinPcap compatible mode). Run terminal as Administrator if needed.

---

### Symptom: PermissionError on Linux

**Cause:** Insufficient capability to capture.

**Fix:**

```bash
sudo setcap cap_net_raw,cap_net_admin=eip $(readlink -f $(which python3))
# or run with appropriate user/group permissions for raw sockets
```

---

### Symptom: Pipeline `status: running` but 0 packets

**Cause:** Wrong interface, BPF filter too strict (`filter_expr=ip` excludes non-IP), or no traffic.

**Fix:** Test with `dry_run=true`, relax filter, generate traffic (e.g. `scripts/demo_attack_simulation.ps1`).

---

### Symptom: Sniffer already running

```json
{ "status": "error", "message": "Sniffer is already running" }
```

**Fix:**

```bash
curl -X POST http://localhost:8000/api/sniffer/stop -H "X-API-Key: $API_KEY"
```

If stuck, restart Uvicorn process (singleton coordinator state).

---

## 7. WebSocket failures

### Symptom: Clients never receive alerts

**Checks:**

1. Is pipeline running? `GET /api/sniffer/status`
2. Are attacks detected? Check logs for `ALERT:` lines
3. Is bridge running? Started in lifespan — check logs for `Alert broadcast consumer started`
4. Queue drops? `dropped_total` in bridge stats (not exposed via HTTP — add logging or debug)

**Cause:** Queue full (10,000) — alerts dropped with warning.

**Fix:** Reduce alert rate (cooldown), add WS consumers that read faster, or increase `maxsize` in code.

---

### Symptom: Connection drops immediately

**Cause:** Proxy not configured for WebSocket upgrade.

**Fix:** Configure nginx/load balancer for `Upgrade: websocket` (nginx config not in repo).

---

## 8. API authentication failures

### Symptom: 401 on sniffer endpoints

```json
{ "detail": "Invalid or missing API key" }
```

**Fix:**

```http
X-API-Key: <exact value from .env API_KEY>
```

**Verify:** No trailing whitespace; compare with `echo $API_KEY`.

---

### Symptom: 429 Too Many Requests

**Cause:** Rate limit exceeded on sniffer/whitelist/xai.

**Fix:** Wait `retry_after_seconds` or restart process to clear in-memory windows (test only).

---

## 9. Model loading failures (legacy API)

### Symptom: `503 ML model not loaded` on `/api/predictions/`

**Cause:** Global `ml_model` in `legacy_routes.py` never loaded.

**Fix:**

```bash
curl -X POST http://localhost:8000/api/models/load/1
# Requires row in `models` table with valid file_path
```

This path is **separate** from pipeline `ModelLoader`.

---

## 10. XAI / SHAP errors

| HTTP | Error | Cause |
|------|-------|-------|
| 422 | FeatureContractError | Wrong feature keys/count |
| 400 | UnsupportedModelError | Non-tree model (e.g. LSTM) |
| 500 | ModelLoadError | Missing pkl files |

**Fix:** Use `ensemble` with tree artifacts; send all 20 features from `models/features.json`.

---

## 11. Email alerts not sent

### Symptom: Alerts in DB/WS but no email

**Checks:**

1. `ENABLE_EMAIL_ALERTS=true`
2. Severity `high` or `critical` and confidence ≥ 0.85
3. Not in email cooldown for `src_ip`
4. Valid `SMTP_*` settings

**Cause (architecture):** `AlertManager.generate_alert` calls `email_service.dispatch_alert_email` from **sniffer thread**. `EmailNotificationService` may log:

```
No event loop running; email not dispatched
```

**Fix (operational):** Treat email as best-effort until dispatch moved to asyncio consumer; or trigger email from async context manually.

---

## 12. Docker-specific issues

### Symptom: nginx container fails to start

**Cause:** `./nginx/nginx.conf` (reverse proxy config) does not exist in repository. Note: `frontend/nginx.conf` is for the dashboard container, not the reverse proxy.

**Fix:** Comment out `nginx` service in `docker-compose.yml`, or create `nginx/nginx.conf` with reverse proxy config (see `docs/DEPLOYMENT_GUIDE.md` Section 5.3 for example).

---

### Symptom: Backend healthcheck fails in container

**Cause:** `requests` may not be installed in slim image healthcheck CMD.

**Fix:** Use `curl` healthcheck or install `requests` in Dockerfile.

---

### Symptom: Capture works on host but not in container

**Cause:** Container lacks access to host interfaces.

**Fix:** Use host network mode (not in current compose) or deploy capture on host natively.

---

## 13. Import / module errors

### Symptom: `ModuleNotFoundError: backend.alerts.engine`

**Cause:** Running `backend/ml/inference.py` — module removed.

**Fix:** Use `alert_engine/alert_manager.py` and pipeline path; do not use `inference.py`.

---

## 14. Diagnostic command cheat sheet

```bash
# Service health
curl -s http://localhost:8000/health/detailed | jq

# Sniffer (auth)
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/api/sniffer/status | jq

# Logs
tail -f logs/backend.log

# Tests
pytest backend/tests/test_health_detailed.py -v
pytest backend/tests/test_pipeline_integration.py -m integration -v
pytest backend/tests/test_websocket_broadcast.py -v

# Config
python backend/scripts/verify_config_security.py
```

---

## 15. When to restart the process

Restart Uvicorn when:

- Singleton coordinator/sniffer stuck after failed stop
- Model artifacts replaced on disk (loader may need re-init)
- Rate limit windows need reset in dev
- Changed `.env` production secrets

---

## 16. Related documentation

- `docs/DEPLOYMENT_GUIDE.md`
- `docs/PIPELINE_FLOW.md`
- `docs/SECURITY_MODEL.md`
- `docs/ML_PIPELINE.md`
