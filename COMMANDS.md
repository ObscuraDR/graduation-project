# IDS Backend - Runnable Commands

## Prerequisites

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Initialize database:
```bash
python backend/database/init_db.py
```

## Run Commands

### 1. Start Backend + DB using Docker Compose

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f ids-backend

# Stop services
docker-compose down
```

### 2. Run Packet Sniffer (Standalone)

#### Windows Setup (Required for Packet Sniffing)

**Npcap Installation:**
```powershell
# Download Npcap from: https://npcap.com/
# IMPORTANT: Select "Install Npcap in WinPcap API-compatible Mode" during installation
# This is required for Scapy to work properly on Windows
```

**List Available Interfaces:**
```powershell
# Run the interface discovery tool
python scripts/list_interfaces.py

# This will show all available sniffable interfaces with recommendations
# Common Windows interface names: "Wi-Fi", "Ethernet", "Local Area Connection"
```

**Run Sniffer:**
```bash
# Run on default interface (eth0 - may not work on Windows)
python run_sniffer.py

# Run on specific Windows interface
python run_sniffer.py --interface "Wi-Fi"

# Run with custom filter
python run_sniffer.py --interface "Ethernet" --filter "tcp port 80"

# Run for specific duration
python run_sniffer.py --duration 300

# Run with specific model
python run_sniffer.py --model ensemble
```

**Dry Run Mode (Testing):**
```powershell
# Test packet capture for 3 seconds without running full ML pipeline
curl -X POST "http://localhost:8000/api/sniffer/start?interface=Wi-Fi&dry_run=true" `
     -H "X-API-Key: supersecretkey"

# This will return packet_count and success status
# Useful for verifying interface permissions and Npcap installation
```

### 3. Run Backend API

```bash
# Run with uvicorn
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Or run main.py directly
python backend/main.py
```

### 4. Regenerate Dummy Ensemble Models (development / demo)

`ModelLoader.load_from_directory("ensemble")` requires these files under `models/`:

| File | Purpose |
|------|---------|
| `ensemble.pkl` | Classifier (trained on scaled 20-D features) |
| `ensemble_scaler.pkl` | `StandardScaler` fitted on 20 features |
| `ensemble_encoder.pkl` | `LabelEncoder` for attack class names |

```bash
# From project root — creates the three files above and removes legacy names
python backend/ml/create_dummy_models.py

# Validate features.json vs feature_extractor.py
python scripts/validate_features.py

# Smoke-test load + predict_flow
python scripts/test_predictor.py

# List models directory (PowerShell)
Get-ChildItem models
```

**Cleanup only** (if you need to remove stale artifacts manually):

```powershell
Remove-Item -ErrorAction SilentlyContinue models/scaler.pkl, models/label_encoder.pkl, models/random_forest.pkl, models/xgboost.pkl, models/lstm.pkl
```

Expected `models/` contents after regenerate:

```
features.json
ensemble.pkl
ensemble_scaler.pkl
ensemble_encoder.pkl
.gitkeep
```

### 5. Preprocess CICIDS2017 Dataset

Before training, the raw CICIDS2017 dataset must be preprocessed to align with the 20-feature IDS contract. This script handles chunked loading, NaN/inf cleaning, and label mapping.

```bash
# Preprocess the dataset (assuming raw files are in data/cicids2017/)
python scripts/preprocess_cicids2017.py \
  --input-dir data/cicids2017 \
  --output data/cicids2017_processed.csv

# View the generated preprocessing report
cat reports/cicids2017_preprocess_report.json
```

### 6. Train ML Models (CICIDS2017 data)

Ensure you have run the preprocessing script first. The training script now enforces a strict feature contract.

```bash
# Train ensemble model on the processed dataset
python backend/ml/train_flow_model.py \
  --data data/cicids2017_processed.csv \
  --model ensemble

# Train Random Forest
python backend/ml/train_flow_model.py \
  --data data/cicids2017_processed.csv \
  --model rf

# Train XGBoost
python backend/ml/train_flow_model.py \
  --data data/cicids2017_processed.csv \
  --model xgb

# Check the evaluation report
cat reports/cicids2017_training_report.json
```

### 7. Test Attack Simulation

```bash
# Port scan simulation (requires nmap)
nmap -sS -p 1-1000 <target_ip>

# Ping flood (requires hping3)
hping3 -i u1000 <target_ip>

# Brute force (requires hydra)
hydra -l admin -P passwords.txt ssh://<target_ip>
```

### 8. API Testing

```bash
# Health check
curl http://localhost:8000/health

# Sniffer control (full ML pipeline — only official start/stop API)
# Start with interface validation and dry run mode
curl -X POST "http://localhost:8000/api/sniffer/start?interface=Wi-Fi&filter_expr=ip&model_name=ensemble&min_packets=10&dry_run=false" \
     -H "X-API-Key: supersecretkey"

# Dry run mode (test capture for 3 seconds)
curl -X POST "http://localhost:8000/api/sniffer/start?interface=Wi-Fi&dry_run=true" \
     -H "X-API-Key: supersecretkey"

# Check status
curl http://localhost:8000/api/sniffer/status \
     -H "X-API-Key: supersecretkey"

# Stop sniffer
curl -X POST http://localhost:8000/api/sniffer/stop \
     -H "X-API-Key: supersecretkey"

# Traffic monitoring (read-only)
curl http://localhost:8000/api/traffic/stats
curl http://localhost:8000/api/traffic/flows
curl http://localhost:8000/api/traffic/top-talkers

# Alerts
curl http://localhost:8000/api/alerts/

# Whitelist
curl http://localhost:8000/api/whitelist/list

# XAI Explanation
curl -X POST http://localhost:8000/api/xai/explain \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "ensemble",
    "features": {
      "flow_duration": 1500.5,
      "total_fwd_packets": 10,
      "total_bwd_packets": 8,
      "total_fwd_bytes": 1024,
      "total_bwd_bytes": 2048,
      "avg_packet_size": 200,
      "packet_rate": 50,
      "byte_rate": 5000,
      "syn_count": 2,
      "fin_count": 1,
      "rst_count": 0,
      "psh_count": 5,
      "ack_count": 15,
      "unique_dst_ports": 2,
      "inter_arrival_time_mean": 10.5,
      "fwd_packet_rate": 25,
      "bwd_packet_rate": 25,
      "fwd_byte_rate": 2500,
      "bwd_byte_rate": 2500,
      "packet_length_mean": 150
    }
  }'
```

OpenAPI: http://localhost:8000/docs — sniffer routes appear only under tag **sniffer**.

### 9. Email Alert Notifications

#### 8.1 Configure SMTP credentials

Edit `.env` (copy from `.env.example` if not done yet):

```ini
# Enable or disable email alerts globally
ENABLE_EMAIL_ALERTS=true

# SMTP server settings
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-gmail@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_FROM=Z-Sentinel IDS <your-gmail@gmail.com>

# One or more recipients, comma-separated
SMTP_TO=soc-lead@yourorg.com,analyst@yourorg.com

# Cooldown: minimum seconds between emails for the same attacker IP
EMAIL_COOLDOWN_SECONDS=60
```

> **Gmail App Password** (required when 2FA is enabled):
> 1. Go to https://myaccount.google.com/apppasswords
> 2. Select app → "Mail", device → "Other" → type `IDS`
> 3. Copy the generated 16-character password into `SMTP_PASSWORD`

#### 8.2 Email gate rules

An email is sent **only when all four conditions are true**:

| Condition | Value |
|-----------|-------|
| `ENABLE_EMAIL_ALERTS` | `true` |
| `severity` | `high` or `critical` |
| `confidence` | ≥ 0.85 |
| Attacker IP cooldown | elapsed (default 60 s) |

#### 8.3 Install the SMTP dependency

```bash
pip install aiosmtplib
# already in requirements.txt – listed for reference
```

#### 8.4 Quick smoke-test (no real SMTP)

Patch the service in a Python shell to verify gating logic:

```python
import asyncio
from unittest.mock import patch, AsyncMock
from backend.notifications.email import EmailNotificationService

svc = EmailNotificationService(cooldown_seconds=60)
alert = {
    "alert_id": "demo-001",
    "attack_type": "DDoS",
    "severity": "critical",
    "confidence": 0.97,
    "src_ip": "10.0.0.1",
    "dst_ip": "192.168.1.1",
    "src_port": 54321,
    "dst_port": 80,
    "protocol": "TCP",
    "timestamp": "2026-05-19T10:00:00",
}

with patch("backend.notifications.email.settings") as s, \
     patch("backend.notifications.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
    s.enable_email_alerts = True
    s.email_cooldown_seconds = 60
    s.smtp_host = "smtp.gmail.com"
    s.smtp_port = 587
    s.smtp_user = "u"
    s.smtp_password = "p"
    s.smtp_from = "IDS <ids@example.com>"
    s.smtp_to = "soc@example.com"

    print("Gate check:", svc.should_send_email(alert))   # → True
    asyncio.run(svc.send_alert_email(alert))
    print("SMTP called:", mock_send.called)               # → True
```

#### 8.5 Trigger a real alert via API (demo)

Start the backend, then POST a manual high-severity alert:

```bash
# 1. Start the backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 2. Health check
curl http://localhost:8000/health

# 3. Start the IDS sniffer pipeline
curl -X POST "http://localhost:8000/api/sniffer/start?interface=eth0&model_name=ensemble&min_packets=10" \
     -H "X-API-Key: supersecretkey"

# 4. Check alerts (after traffic is captured)
curl http://localhost:8000/api/alerts/ \
     -H "X-API-Key: supersecretkey"

# 5. Manually inspect email dispatch logs
# Look for lines like:
#   INFO  backend.notifications.email - Email sent to ['soc@...'] | subject: [IDS Alert] CRITICAL: DDoS...
#   DEBUG backend.notifications.email - Email suppressed (cooldown) for IP 10.0.0.1
```

#### 8.6 Adjust cooldown at runtime (Python shell)

```python
from backend.notifications.email import email_service

# Clear cooldown for a specific attacker IP
email_service.reset_cooldown("10.0.0.1")

# Clear all cooldown state
email_service.reset_cooldown()
```

### 10. Run Tests

```bash
# Run all tests
pytest backend/tests/

# Run with coverage
pytest backend/tests/ --cov=backend --cov-report=html

# Run only email alert tests (16 cases, zero SMTP calls)
pytest backend/tests/test_email_alerts.py -v

# Run alert manager tests
pytest backend/tests/test_alerts.py -v

# Run by marker
pytest backend/tests/ -m unit
```

## API Endpoints

### Sniffer Control (full ML pipeline)
- `POST /api/sniffer/start` - Start IDS pipeline (capture → flows → ML → alerts)
- `POST /api/sniffer/stop` - Stop IDS pipeline
- `GET /api/sniffer/status` - Pipeline status and statistics

### Traffic Monitoring (read-only)
- `GET /api/traffic/stats` - Flow + pipeline monitoring snapshot
- `GET /api/traffic/flows` - Active flows
- `GET /api/traffic/flows/{src_ip}` - Flows by source IP
- `GET /api/traffic/top-talkers` - Top source IPs by packet count
- `POST /api/traffic/flows/cleanup` - Remove expired flows from memory (maintenance)

### Alert Endpoints
- `GET /api/alerts` - Get all alerts
- `GET /api/alerts/{alert_id}` - Get specific alert
- `PUT /api/alerts/{alert_id}/resolve` - Resolve alert
- `DELETE /api/alerts/{alert_id}` - Delete alert

### Prediction Endpoints
- `POST /api/predictions` - Single prediction
- `POST /api/predictions/batch` - Batch prediction

### Model Endpoints
- `GET /api/models` - Get all models
- `POST /api/models/load/{model_id}` - Load model

### WebSocket
- `ws://localhost:8000/ws` - Real-time updates

## Definition of Done

- [x] Packet sniffer implemented (capture_engine/packet_sniffer.py)
- [x] Flow builder implemented (flow_engine/flow_builder.py)
- [x] Feature extractor implemented (feature_engine/feature_extractor.py)
- [x] Model loader implemented (detection_engine/model_loader.py)
- [x] Predictor implemented (detection_engine/predictor.py)
- [x] Alert manager implemented (alert_engine/alert_manager.py)
- [x] Traffic API routes implemented (api/routes/traffic.py)
- [x] Main.py updated with new modules
- [x] Runnable sniffer script created (run_sniffer.py)
- [x] Commands documented (COMMANDS.md)
- [x] Email alert notifications integrated (notifications/email.py)
- [x] Email gate: severity high|critical + confidence ≥ 0.85
- [x] Email cooldown per attacker IP (EMAIL_COOLDOWN_SECONDS)
- [x] Non-blocking email dispatch (asyncio.create_task)
- [x] Unit tests for email alerts (tests/test_email_alerts.py – 16 cases, no real SMTP)

## FINAL DEMO COMMANDS

### Full End-to-End Demo Automation

For thesis defense, use the automated PowerShell script to run the complete demo:

```powershell
# Run full demo with auto-detected interface
.\scripts\demo_full.ps1

# Run with specific interface
.\scripts\demo_full.ps1 -Interface "Wi-Fi"

# Run with custom API key and port
.\scripts\demo_full.ps1 -Interface "Ethernet" -ApiKey "my-secret-key" -Port 8000

# Run with longer sniffer duration
.\scripts\demo_full.ps1 -Interface "Wi-Fi" -RunDurationSec 30

# Skip Docker (if database already running)
.\scripts\demo_full.ps1 -Interface "Wi-Fi" -SkipDocker

# Skip sniffer (for backend-only demo)
.\scripts\demo_full.ps1 -SkipSniffer
```

### Attack Simulation Instructions

To generate attack traffic for IDS detection:

```powershell
# View attack simulation instructions
.\scripts\demo_attack_simulation.ps1
```

The attack simulation script provides commands for:
- **Port Scan** (Nmap): `nmap -sS -p 1-1000 <target_ip>`
- **DDoS/Flood** (hping3): `hping3 -i u1000 <target_ip>`
- **Brute Force** (Hydra): `hydra -l admin -P passwords.txt ssh://<target_ip>`

### Demo Workflow for Thesis Defense

1. **Start the full demo:**
   ```powershell
   .\scripts\demo_full.ps1 -Interface "Wi-Fi"
   ```

2. **In a separate terminal, connect to WebSocket:**
   ```powershell
   wscat -c ws://localhost:8000/ws
   ```

3. **Generate attack traffic (in another terminal):**
   ```powershell
   nmap -sS -p 1-1000 127.0.0.1
   ```

4. **Observe real-time alerts in WebSocket terminal**

5. **Verify alerts via API:**
   ```powershell
   curl http://localhost:8000/api/alerts/ -H "X-API-Key: your-key"
   ```

### Expected Screenshots for Thesis Defense

Capture these screenshots during the demo:

1. **Environment Validation** - All checks showing [PASS]
2. **Database Initialization** - Success message
3. **Backend Health Check** - `/health` returning 200 OK
4. **API Security Test** - 401 without key, 200 with key
5. **Interface Discovery** - List of interfaces with recommended one highlighted
6. **Sniffer Start** - Success response with interface name
7. **Packet Count Monitoring** - Increasing packet count over time
8. **Alerts Display** - JSON response showing captured alerts
9. **WebSocket Connection** - Connected to `ws://localhost:8000/ws`
10. **Real-time Alert Stream** - Alerts appearing in WebSocket terminal during attack
11. **Attack Command Output** - Nmap/hping3/hydra command execution
12. **Alert Details** - Attack type, severity, confidence, IPs, timestamp
13. **Clean Shutdown** - All processes stopped cleanly

### Quick Demo (No Attack Traffic)

For a quick demo without generating attacks:

```powershell
# Run demo with short duration
.\scripts\demo_full.ps1 -Interface "Wi-Fi" -RunDurationSec 10
```

This will demonstrate:
- Environment setup
- Database initialization
- Backend startup
- API security
- Interface discovery
- Sniffer start/stop
- Packet capture (normal traffic)
- Clean shutdown

### Full Demo with Attack Detection

For complete IDS detection demonstration:

```powershell
# Terminal 1: Start full demo
.\scripts\demo_full.ps1 -Interface "Wi-Fi" -RunDurationSec 30

# Terminal 2: Connect to WebSocket
wscat -c ws://localhost:8000/ws

# Terminal 3: Generate attack traffic
nmap -sS -p 1-1000 127.0.0.1
```

This will demonstrate:
- All quick demo features
- Real-time alert streaming
- Attack detection and classification
- Alert persistence in database

## Next Steps

1. Download CICIDS2017 dataset
2. Train models using training script
3. Test with real network traffic
4. Integrate with frontend dashboard

## 11. Rate Limiting

The API enforces per-client-IP sliding-window rate limits on sensitive endpoint groups.

### Limits

| Endpoint group     | Limit            |
|--------------------|------------------|
| `/api/sniffer/*`   | 10 req / 60 s    |
| `/api/whitelist/*` | 30 req / 60 s    |
| `/api/xai/*`       | 60 req / 60 s    |
| All other routes   | No limit applied |

Limits are tracked in-memory per client IP. The client IP is read from the
`X-Forwarded-For` header (first entry) when present, otherwise from the TCP
remote address.

### HTTP 429 Response

When a limit is exceeded the server returns:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 42
Content-Type: application/json

{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Limit: 10 req/60s per IP.",
  "retry_after_seconds": 42
}
```

### Example – triggering 429 on /api/sniffer/status

```bash
# Send 11 rapid requests from the same IP (limit is 10/60s)
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    http://localhost:8000/api/sniffer/status \
    -H "X-API-Key: supersecretkey"
done
# Output: 200 200 200 200 200 200 200 200 200 200 429
```

PowerShell equivalent:

```powershell
1..11 | ForEach-Object {
    $r = Invoke-WebRequest -Uri "http://localhost:8000/api/sniffer/status" `
         -Headers @{"X-API-Key"="supersecretkey"} -SkipHttpErrorCheck
    Write-Host "Request $_`: $($r.StatusCode)"
}
# Request 11: 429
```

### Example – 429 response body

```bash
curl -i http://localhost:8000/api/sniffer/status \
     -H "X-API-Key: supersecretkey"
# HTTP/1.1 429 Too Many Requests
# retry-after: 58
# {"error":"rate_limit_exceeded","message":"Too many requests. Limit: 10 req/60s per IP.","retry_after_seconds":58}
```

---

## 12. Input Validation

All endpoints that accept IP addresses, ports, protocols, or interface names
enforce strict validation before any business logic runs.

### Rules

| Field           | Rule                                              | Error  |
|-----------------|---------------------------------------------------|--------|
| `ip_address`    | Valid dotted-decimal IPv4 (0–255 per octet)       | 422    |
| `port`          | Integer 1–65535                                   | 422    |
| `protocol`      | One of `tcp`, `udp`, `icmp` (case-insensitive)    | 422    |
| `interface`     | Alphanumeric + space/hyphen/underscore/dot, ≤ 64 chars | 422 |

### Affected endpoints

- `POST /api/whitelist/add` — validates `ip_address`, `port`, `protocol`
- `POST /api/whitelist/remove` — validates `ip_address` when provided
- `POST /api/sniffer/start` — validates `interface` (injection safety), `min_packets` (1–10000), `prediction_mode` (once|window)

### Example – invalid IP rejected

```bash
curl -X POST http://localhost:8000/api/whitelist/add \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecretkey" \
  -d '{"ip_address": "999.999.999.999"}'
# HTTP 422
# {"detail":[{"msg":"Invalid IPv4 address: '999.999.999.999'", ...}]}
```

### Example – injection attempt blocked

```bash
curl -X POST "http://localhost:8000/api/sniffer/start?interface=eth0;rm+-rf+/" \
  -H "X-API-Key: supersecretkey"
# HTTP 422
# {"detail":"Interface name 'eth0;rm -rf /' contains invalid characters."}
```

### Run security tests

```bash
# Rate limiting tests (11 tests)
pytest backend/tests/test_rate_limiting.py -v

# Input validation tests (47 tests)
pytest backend/tests/test_input_validation.py -v

# Both together
pytest backend/tests/test_rate_limiting.py backend/tests/test_input_validation.py -v
```

---

## 13. MongoDB + Redis Integration

### Docker Compose — start all services (including authenticated Mongo + Redis)

```bash
# Start all services
docker-compose up -d

# Verify all containers are healthy
docker-compose ps

# Tail backend logs
docker-compose logs -f ids-backend

# Stop and remove containers (keep volumes)
docker-compose down

# Stop and wipe all volumes (full reset)
docker-compose down -v
```

Default demo credentials (local only — change before any real deployment):

| Service  | Username         | Password         |
|----------|------------------|------------------|
| MongoDB  | ids_mongo_user   | ids_mongo_pass   |
| Redis    | —                | ids_redis_pass   |

### Environment variables added

Copy `.env.example` to `.env` and set the URI overrides for local non-Docker use:

```ini
# MongoDB — URI takes priority over MONGODB_HOST/PORT when non-empty
MONGO_URI=mongodb://ids_mongo_user:ids_mongo_pass@localhost:27017/ids_logs?authSource=admin
MONGO_DB=ids_logs

# Redis — URI takes priority over REDIS_HOST/PORT when non-empty
REDIS_URL=redis://:ids_redis_pass@localhost:6379/0
```

Leave both empty to fall back to the individual `MONGODB_HOST` / `REDIS_HOST` fields (unauthenticated, for local dev without Docker).

### Verify MongoDB connection

```bash
python scripts/test_mongo_connection.py
# Expected: [PASS] MongoDB: insert/read/delete OK (db=ids_logs, collection=ids_healthcheck)
```

### Verify Redis connection

```bash
python scripts/test_redis_connection.py
# Expected: [PASS] Redis: set/get/delete OK (key=ids:healthcheck)
```

### Test /health/detailed endpoint

```bash
curl http://localhost:8000/health/detailed
```

Expected response (all services up):

```json
{
  "postgres": {"connected": true},
  "redis":    {"connected": true},
  "mongo":    {"connected": true},
  "model_loaded": true,
  "pipeline_running": false,
  "timestamp": "2026-05-20T10:00:00.000000+00:00"
}
```

### Run health detailed tests (no Docker required)

```bash
pytest backend/tests/test_health_detailed.py -v
```

### Real integration behaviour

- **MongoDB** (`flow_logs` collection): every attack flow detected by the ML pipeline is logged with fields `flow_id`, `src_ip`, `dst_ip`, `src_port`, `dst_port`, `protocol`, `timestamp`, `features`. Logging is fire-and-forget — a MongoDB outage does not crash the pipeline.
- **Redis** (alert cooldown): `AlertManager` stores per-IP cooldown state as TTL keys (`alert_cooldown:<ip>`) in Redis. If Redis is unavailable the manager falls back to in-memory `datetime` tracking transparently.
