# Z-Sentinel IDS — Command Reference

Tất cả lệnh cần thiết để phát triển, test, và demo hệ thống.

---

## 1. Setup

```bash
# Cài dependencies
pip install -r requirements.txt

# Cấu hình environment
cp .env.example .env
# Chỉnh sửa .env với thông tin của bạn

# Tạo dummy models (cho dev/demo — không cần dataset thật)
python backend/ml/create_dummy_models.py

# Validate feature contract
python backend/scripts/validate_features.py

# Smoke-test model loading + predict
python backend/scripts/test_predictor.py
```

---

## 2. Docker Compose

```bash
# Start tất cả services
docker compose up -d

# Chỉ start databases (cho local dev)
docker compose up -d postgres mongodb redis

# Kiểm tra trạng thái
docker compose ps

# Xem logs backend
docker compose logs -f ids-backend

# Xem logs tất cả
docker compose logs -f

# Restart backend
docker compose restart ids-backend

# Dừng (giữ volumes)
docker compose down

# Dừng và xóa volumes (CẢNH BÁO: mất toàn bộ data)
docker compose down -v

# Rebuild image
docker compose build --no-cache ids-backend
```

---

## 3. Chạy Backend

```bash
# Development (với reload)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Production (không reload, không access log)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log

# Hoặc chạy trực tiếp
python backend/main.py
```

---

## 4. Windows — Packet Capture Setup

```powershell
# Cài Npcap (bắt buộc cho Windows)
# Download từ: https://npcap.com/
# QUAN TRỌNG: Chọn "Install Npcap in WinPcap API-compatible Mode"

# Liệt kê interfaces có sẵn
python backend/scripts/list_interfaces.py

# Ví dụ output:
# [0] Wi-Fi
# [1] Ethernet
# [2] Loopback Pseudo-Interface 1
```

---

## 5. API Testing

### Health

```bash
# Basic health
curl http://localhost:8000/health

# Detailed health (tất cả services)
curl http://localhost:8000/health/detailed
```

### Sniffer Control (yêu cầu X-API-Key)

```bash
# Start pipeline
curl -X POST "http://localhost:8000/api/sniffer/start?interface=eth0&model_name=ensemble&min_packets=10" \
     -H "X-API-Key: your-api-key"

# Start với dry run (test 3 giây)
curl -X POST "http://localhost:8000/api/sniffer/start?interface=eth0&dry_run=true" \
     -H "X-API-Key: your-api-key"

# Kiểm tra trạng thái
curl http://localhost:8000/api/sniffer/status \
     -H "X-API-Key: your-api-key"

# Dừng pipeline
curl -X POST http://localhost:8000/api/sniffer/stop \
     -H "X-API-Key: your-api-key"
```

**PowerShell:**
```powershell
# Start
Invoke-WebRequest -Uri "http://localhost:8000/api/sniffer/start?interface=Wi-Fi&model_name=ensemble" `
    -Method POST -Headers @{"X-API-Key"="your-api-key"}

# Status
Invoke-WebRequest -Uri "http://localhost:8000/api/sniffer/status" `
    -Headers @{"X-API-Key"="your-api-key"}
```

### Traffic Monitoring (không cần API key)

```bash
curl http://localhost:8000/api/traffic/stats
curl http://localhost:8000/api/traffic/flows
curl http://localhost:8000/api/traffic/top-talkers
curl -X POST http://localhost:8000/api/traffic/flows/cleanup
```

### Alerts

```bash
# Tất cả alerts
curl http://localhost:8000/api/alerts/

# Lọc theo severity
curl "http://localhost:8000/api/alerts/?severity=critical&limit=20"

# Lọc theo status
curl "http://localhost:8000/api/alerts/?status=active"

# Chi tiết một alert
curl http://localhost:8000/api/alerts/{alert_id}

# Resolve alert
curl -X PUT "http://localhost:8000/api/alerts/{alert_id}/resolve?notes=Investigated"

# Xóa alert
curl -X DELETE http://localhost:8000/api/alerts/{alert_id}
```

### Whitelist

```bash
# Xem danh sách
curl http://localhost:8000/api/whitelist/list

# Thêm IP
curl -X POST http://localhost:8000/api/whitelist/add \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-api-key" \
     -d '{"ip_address": "192.168.1.100", "reason": "Internal server"}'

# Xóa theo IP
curl -X POST http://localhost:8000/api/whitelist/remove \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-api-key" \
     -d '{"ip_address": "192.168.1.100"}'

# Xóa theo ID
curl -X POST http://localhost:8000/api/whitelist/remove \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-api-key" \
     -d '{"whitelist_id": 1}'
```

### XAI — SHAP Explanation

```bash
curl -X POST http://localhost:8000/api/xai/explain \
     -H "Content-Type: application/json" \
     -d '{
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
     }'
```

### Statistics

```bash
curl http://localhost:8000/api/stats/alert-engine
curl http://localhost:8000/api/stats/system
```

### WebSocket

```bash
# Cài wscat
npm install -g wscat

# Kết nối
wscat -c ws://localhost:8000/ws
```

---

## 6. Rate Limiting Test

```bash
# Gửi 11 requests liên tiếp (limit là 10/60s)
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    http://localhost:8000/api/sniffer/status \
    -H "X-API-Key: your-api-key"
done
# Output: 200 200 200 200 200 200 200 200 200 200 429
```

**PowerShell:**
```powershell
1..11 | ForEach-Object {
    $r = Invoke-WebRequest -Uri "http://localhost:8000/api/sniffer/status" `
         -Headers @{"X-API-Key"="your-api-key"} -SkipHttpErrorCheck
    Write-Host "Request $_`: $($r.StatusCode)"
}
```

---

## 7. Models

### Tạo dummy models (dev/demo)

```bash
# Tạo 3 files: ensemble.pkl, ensemble_scaler.pkl, ensemble_encoder.pkl, features.json
python backend/ml/create_dummy_models.py

# Kiểm tra
dir models\
# Phải có: ensemble.pkl, ensemble_scaler.pkl, ensemble_encoder.pkl, features.json
```

### Xóa legacy artifacts

```powershell
Remove-Item -ErrorAction SilentlyContinue `
    models/scaler.pkl, models/label_encoder.pkl, `
    models/random_forest.pkl, models/xgboost.pkl, models/lstm.pkl
```

### Train từ CICIDS2017

```bash
# Bước 1: Preprocess dataset
python backend/scripts/preprocess_cicids2017.py \
  --input-dir backend/data/cicids2017 \
  --output backend/data/cicids2017_processed.csv

# Bước 2: Train model
python backend/ml/train_flow_model.py \
  --data data/cicids2017_processed.csv \
  --model ensemble

# Bước 3: Kiểm tra kết quả
cat backend/reports/cicids2017_training_report.json
```

**PowerShell automation:**
```powershell
.\scripts\train_cicids2017.ps1 -InputDir "path\to\cicids2017" -ModelType "ensemble"
```

---

## 8. Tests

```bash
# Chạy tất cả tests
pytest backend/tests/ -v

# Với coverage
pytest backend/tests/ --cov=backend --cov-report=html

# Chỉ unit tests
pytest backend/tests/ -m unit -v

# Test cụ thể
pytest backend/tests/test_email_alerts.py -v
pytest backend/tests/test_api_security.py -v
pytest backend/tests/test_feature_contract.py -v
pytest backend/tests/test_health_detailed.py -v

# Test rate limiting
pytest backend/tests/test_api_security.py -v -k "rate"

# Bỏ qua integration tests (cần DB)
pytest backend/tests/ -v -m "not integration"
```

---

## 9. Database

### Khởi tạo tables

```bash
# Option 1: Alembic migrations (recommended)
alembic upgrade head

# Option 2: Legacy init script
python backend/database/init_db.py
```

### Tạo migration mới (khi thay đổi models.py)

```bash
alembic revision --autogenerate -m "description of change"
alembic upgrade head
```

### Kiểm tra PostgreSQL

```bash
# Kết nối
docker exec -it ids-postgres psql -U ids_user -d ids_db

# Liệt kê tables
\dt

# Xem alerts gần nhất
SELECT id, attack_type, severity, confidence, source_ip, timestamp
FROM attack_alerts
ORDER BY timestamp DESC
LIMIT 10;

# Xem flows
SELECT id, src_ip, dst_ip, protocol, packet_count
FROM traffic_flows
ORDER BY id DESC
LIMIT 10;
```

### Kiểm tra MongoDB

```bash
docker exec -it ids-mongodb mongosh \
  --username ids_mongo_user --password ids_mongo_pass \
  --authenticationDatabase admin

# Trong mongosh:
use ids_logs
db.flow_logs.find().limit(5).pretty()
db.flow_logs.countDocuments()
```

### Kiểm tra Redis

```bash
docker exec -it ids-redis redis-cli -a ids_redis_pass

# Trong redis-cli:
KEYS alert_cooldown:*
TTL alert_cooldown:192.168.1.100
```

### Verify connections

```bash
python backend/scripts/test_mongo_connection.py
python backend/scripts/test_redis_connection.py
```

---

## 10. Email Alerts

### Cấu hình Gmail

```ini
# .env
ENABLE_EMAIL_ALERTS=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-gmail@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx   # 16-char App Password
SMTP_FROM=Z-Sentinel IDS <your-gmail@gmail.com>
SMTP_TO=recipient@example.com
EMAIL_COOLDOWN_SECONDS=60
```

> **Gmail App Password:** https://myaccount.google.com/apppasswords → Mail → Other → "IDS"

### Email gate rules

Email chỉ gửi khi **tất cả** điều kiện đúng:

| Điều kiện | Giá trị |
|---|---|
| `ENABLE_EMAIL_ALERTS` | `true` |
| `severity` | `high` hoặc `critical` |
| `confidence` | ≥ 0.85 |
| IP cooldown | đã hết (default 60s) |

### Smoke test (không cần SMTP thật)

```python
from unittest.mock import patch, AsyncMock
from backend.notifications.email import EmailNotificationService
import asyncio

svc = EmailNotificationService(cooldown_seconds=60)
alert = {
    "alert_id": "test-001", "attack_type": "DDoS",
    "severity": "critical", "confidence": 0.97,
    "src_ip": "10.0.0.1", "dst_ip": "192.168.1.1",
    "src_port": 54321, "dst_port": 80,
    "protocol": "TCP", "timestamp": "2026-05-22T10:00:00",
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

### Reset cooldown

```python
from backend.notifications.email import email_service

email_service.reset_cooldown("10.0.0.1")   # Reset một IP
email_service.reset_cooldown()              # Reset tất cả
```

---

## 11. Attack Simulation (Demo)

```bash
# Port scan (cần nmap)
nmap -sS -p 1-1000 <target_ip>

# DDoS/Flood (cần hping3)
hping3 -i u1000 <target_ip>

# Brute force (cần hydra)
hydra -l admin -P passwords.txt ssh://<target_ip>
```

**PowerShell automation:**
```powershell
# Xem hướng dẫn attack simulation
.\scripts\demo_attack_simulation.ps1

# Full demo tự động
.\scripts\demo_full.ps1 -Interface "Wi-Fi"
.\scripts\demo_full.ps1 -Interface "Wi-Fi" -RunDurationSec 30
.\scripts\demo_full.ps1 -Interface "Wi-Fi" -SkipDocker
```

---

## 12. Load Testing

```bash
# Chạy Locust (headless)
cd backend/loadtests
locust -f locustfile.py --host=http://localhost:8000 \
       --headless -u 50 -r 5 -t 60s

# Với UI
locust -f locustfile.py --host=http://localhost:8000
# Mở http://localhost:8089
```

---

## 13. Swagger UI

Mở trình duyệt:
- **Frontend Dashboard:** http://localhost:3000
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

---

## 14. Endpoint Summary

### Sniffer (yêu cầu X-API-Key)
| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/api/sniffer/start` | Khởi động IDS pipeline |
| POST | `/api/sniffer/stop` | Dừng pipeline |
| GET | `/api/sniffer/status` | Trạng thái và stats |

### Traffic (không cần auth)
| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/traffic/stats` | Flow + pipeline snapshot |
| GET | `/api/traffic/flows` | Active flows |
| GET | `/api/traffic/flows/{src_ip}` | Flows theo source IP |
| GET | `/api/traffic/top-talkers` | Top IPs theo packet count |
| POST | `/api/traffic/flows/cleanup` | Xóa expired flows |

### Alerts
| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/alerts/` | Danh sách alerts |
| GET | `/api/alerts/{id}` | Chi tiết alert |
| PUT | `/api/alerts/{id}/resolve` | Resolve alert |
| DELETE | `/api/alerts/{id}` | Xóa alert |

### Whitelist
| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/whitelist/list` | Danh sách whitelist |
| POST | `/api/whitelist/add` | Thêm IP |
| POST | `/api/whitelist/remove` | Xóa IP |

### XAI
| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/api/xai/explain` | SHAP explanation |

### System
| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/health` | Basic health |
| GET | `/health/detailed` | Detailed connectivity |
| GET | `/metrics` | Prometheus metrics |
| GET | `/api/stats/alert-engine` | Alert engine stats |
| GET | `/api/stats/system` | System stats |
| WS | `/ws` | Real-time WebSocket |
