# Z-Sentinel IDS — Deployment Guide

Hướng dẫn triển khai đầy đủ cho IDS Backend.

## Table of Contents

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Cấu hình môi trường](#2-cấu-hình-môi-trường)
3. [Docker Compose Deployment](#3-docker-compose-deployment)
4. [Local Development](#4-local-development)
5. [Security Hardening](#5-security-hardening)
6. [Monitoring & Logging](#6-monitoring--logging)
7. [Backup & Recovery](#7-backup--recovery)
8. [Performance Tuning](#8-performance-tuning)
9. [Troubleshooting](#9-troubleshooting)
10. [Production Checklist](#10-production-checklist)

---

## 1. Yêu cầu hệ thống

### Hardware

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB | 50 GB SSD |
| Network | 100 Mbps NIC | Gigabit NIC |

### Software

- Docker 20.10+ và Docker Compose 2.0+
- Python 3.10+ (chỉ cần cho local dev)
- **Windows:** Npcap (WinPcap-compatible mode) — bắt buộc cho packet capture
- **Linux:** libpcap-dev (`apt install libpcap-dev`)

---

## 2. Cấu hình môi trường

### Tạo file .env

```bash
cp .env.example .env
```

### Sinh secure keys

```bash
# API Key (>= 16 chars)
python -c "import secrets; print(secrets.token_urlsafe(24))"

# JWT Secret Key (>= 32 chars)
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Biến môi trường quan trọng

```ini
# ── Environment ──────────────────────────────────────────
ENVIRONMENT=production          # development | production

# ── Security ─────────────────────────────────────────────
API_KEY=<generated-api-key>     # >= 16 chars, required
SECRET_KEY=<generated-secret>   # >= 32 chars, required

# ── CORS ─────────────────────────────────────────────────
# Production: chỉ domain thực tế, không dùng wildcard
CORS_ORIGINS=https://your-frontend.com,https://admin.your-domain.com
# Development:
# CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# ── PostgreSQL ────────────────────────────────────────────
POSTGRES_HOST=postgres          # service name trong Docker Compose
POSTGRES_PORT=5432
POSTGRES_DB=ids_db
POSTGRES_USER=ids_user
POSTGRES_PASSWORD=<strong-password>

# ── MongoDB ───────────────────────────────────────────────
# URI override (ưu tiên hơn MONGODB_HOST/PORT)
MONGO_URI=mongodb://ids_mongo_user:ids_mongo_pass@mongodb:27017/ids_logs?authSource=admin
MONGO_DB=ids_logs

# ── Redis ─────────────────────────────────────────────────
# URI override (ưu tiên hơn REDIS_HOST/PORT)
REDIS_URL=redis://:ids_redis_pass@redis:6379/0

# ── Email Alerts (optional) ───────────────────────────────
ENABLE_EMAIL_ALERTS=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_FROM=Z-Sentinel IDS <noreply@your-domain.com>
SMTP_TO=soc-team@your-domain.com
EMAIL_COOLDOWN_SECONDS=60

# ── Pipeline Tuning ───────────────────────────────────────
MIN_PACKETS=10
PREDICTION_MODE=once            # once | window
FLOW_EXPIRE_SEC=30
FLOW_MAX_LIFETIME_SEC=60
PROCESSED_FLOW_RETENTION_SEC=45

# ── Alert Thresholds ──────────────────────────────────────
ALERT_THRESHOLD_CRITICAL=0.9
ALERT_THRESHOLD_HIGH=0.7
ALERT_THRESHOLD_MEDIUM=0.5
```

---

## 3. Docker Compose Deployment

### Khởi động tất cả services

```bash
# Build và start
docker compose up -d

# Kiểm tra trạng thái
docker compose ps

# Xem logs
docker compose logs -f ids-backend

# Dừng (giữ volumes)
docker compose down

# Dừng và xóa volumes (CẢNH BÁO: mất toàn bộ data)
docker compose down -v
```

### Kiểm tra health

```bash
# Basic health
curl http://localhost:8000/health

# Detailed health (tất cả services)
curl http://localhost:8000/health/detailed
```

Expected response khi tất cả services up:
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

### Khởi động IDS pipeline

```bash
# Tìm tên interface
python backend/scripts/list_interfaces.py

# Start pipeline
curl -X POST "http://localhost:8000/api/sniffer/start?interface=eth0&model_name=ensemble" \
     -H "X-API-Key: your-api-key"

# Kiểm tra
curl http://localhost:8000/api/sniffer/status \
     -H "X-API-Key: your-api-key"
```

### Services trong Docker Compose

| Service | Image | Port (host) | Mô tả |
|---|---|---|---|
| `ids-backend` | Build từ Dockerfile | 8000 | FastAPI + Uvicorn |
| `postgres` | postgres:14-alpine | 5432 | PostgreSQL database |
| `mongodb` | mongo:6-alpine | 27017 | MongoDB log store |
| `redis` | redis:7-alpine | 6379 | Alert cooldown cache |
| `dashboard` | Build từ frontend/Dockerfile | 3000 | React dashboard (Nginx serve) |
| `nginx` | nginx:alpine | 80, 443 | Reverse proxy (optional) |

> **Lưu ý production:** Xóa port mappings cho PostgreSQL, MongoDB, Redis. Chỉ Nginx cần expose ra ngoài.

### Capabilities cần thiết cho packet capture

```yaml
# docker-compose.yml
ids-backend:
  cap_add:
    - NET_RAW    # Bắt buộc cho Scapy raw socket
    - NET_ADMIN  # Bắt buộc cho interface management
  # KHÔNG dùng privileged: true — NET_RAW + NET_ADMIN là đủ
```

---

## 4. Local Development

### Setup

```bash
# Tạo virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Cài dependencies
pip install -r requirements.txt

# Cấu hình
cp .env.example .env
# Chỉnh sửa .env

# Tạo dummy models
python backend/ml/create_dummy_models.py

# Chỉ start databases (không cần build backend image)
docker compose up -d postgres mongodb redis

# Chạy backend local
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Kết nối databases local (không Docker)

```ini
# .env cho local dev (không Docker)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
MONGO_URI=mongodb://localhost:27017/
REDIS_URL=redis://localhost:6379/0
```

---

## 5. Security Hardening

### 5.1 Không dùng `privileged: true`

```yaml
# SAIIII
privileged: true

# ĐÚNG — chỉ cần 2 capabilities này
cap_add:
  - NET_RAW
  - NET_ADMIN
```

### 5.2 Credentials trong .env (không hardcode)

```yaml
# docker-compose.yml — dùng env vars
environment:
  - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
  - MONGO_INITDB_ROOT_PASSWORD=${MONGO_ROOT_PASSWORD}
```

```ini
# .env (gitignored)
POSTGRES_PASSWORD=<strong-random-password>
MONGO_ROOT_PASSWORD=<strong-random-password>
REDIS_PASSWORD=<strong-random-password>
```

### 5.3 HTTPS với Nginx

```nginx
# nginx/nginx.conf
server {
    listen 443 ssl http2;
    server_name ids.yourcompany.com;

    ssl_certificate     /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://ids-backend:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /ws {
        proxy_pass http://ids-backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

server {
    listen 80;
    server_name ids.yourcompany.com;
    return 301 https://$host$request_uri;
}
```

### 5.4 API Key rotation

```bash
# Sinh key mới
python -c "import secrets; print(secrets.token_urlsafe(24))"

# Cập nhật .env
# API_KEY=<new-key>

# Restart backend
docker compose restart ids-backend
```

### 5.5 Production startup validation

Khi `ENVIRONMENT=production`, backend tự động kiểm tra và **từ chối khởi động** nếu:
- `SECRET_KEY` vẫn là giá trị mặc định
- `API_KEY` vẫn là giá trị mặc định
- `SECRET_KEY` < 32 chars
- `API_KEY` < 16 chars
- `CORS_ORIGINS` trống

---

## 6. Monitoring & Logging

### Prometheus Metrics

Backend expose metrics tại `GET /metrics`. Cấu hình Prometheus scrape:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'ids-backend'
    static_configs:
      - targets: ['ids-backend:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### Structured JSON Logs

Logs được ghi ở định dạng JSON vào `logs/backend.log` và stdout:

```bash
# Xem logs real-time (Docker)
docker compose logs -f ids-backend | python -m json.tool

# Xem logs file
tail -f logs/backend.log | python -m json.tool
```

### Log Rotation

```bash
# /etc/logrotate.d/ids-backend
/path/to/graduation project/logs/backend.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

### Health Check Monitoring

```bash
# Kiểm tra định kỳ (cron)
*/5 * * * * curl -sf http://localhost:8000/health/detailed | python -m json.tool >> /var/log/ids-health.log
```

---

## 7. Backup & Recovery

### PostgreSQL Backup

```bash
# Manual backup
docker exec ids-postgres pg_dump -U ids_user ids_db > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i ids-postgres psql -U ids_user ids_db < backup_20260522.sql

# Automated backup (cron — chạy lúc 2:00 AM hàng ngày)
0 2 * * * docker exec ids-postgres pg_dump -U ids_user ids_db | gzip > /backups/ids_$(date +\%Y\%m\%d).sql.gz
```

### MongoDB Backup

```bash
# Backup
docker exec ids-mongodb mongodump \
  --username ids_mongo_user --password ids_mongo_pass \
  --authenticationDatabase admin \
  --db ids_logs --archive=/tmp/mongo_backup.gz --gzip

docker cp ids-mongodb:/tmp/mongo_backup.gz ./backups/

# Restore
docker cp ./backups/mongo_backup.gz ids-mongodb:/tmp/
docker exec ids-mongodb mongorestore \
  --username ids_mongo_user --password ids_mongo_pass \
  --authenticationDatabase admin \
  --db ids_logs --archive=/tmp/mongo_backup.gz --gzip
```

---

## 8. Performance Tuning

### PostgreSQL

```yaml
# docker-compose.yml
postgres:
  command:
    - "postgres"
    - "-c"
    - "shared_buffers=256MB"
    - "-c"
    - "max_connections=100"
    - "-c"
    - "work_mem=4MB"
    - "-c"
    - "effective_cache_size=1GB"
```

### Redis

```yaml
redis:
  command: >
    redis-server
    --requirepass ${REDIS_PASSWORD}
    --appendonly yes
    --maxmemory 256mb
    --maxmemory-policy allkeys-lru
```

### Pipeline Tuning

| Tham số | Mô tả | Gợi ý |
|---|---|---|
| `MIN_PACKETS` | Số packet tối thiểu để trigger inference | Tăng lên 20-50 để giảm false positives |
| `PREDICTION_MODE` | `once` hoặc `window` | Dùng `once` cho production |
| `FLOW_EXPIRE_SEC` | Thời gian inactive trước khi xóa flow | 30s là hợp lý |
| `FLOW_MAX_LIFETIME_SEC` | Tuổi tối đa của flow | 60s |

### Uvicorn Production Command

```bash
# Production (không dùng --reload)
uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --no-access-log \
  --log-level warning
```

> **Tại sao `--workers 1`?** Hệ thống dùng module-level singletons (FlowBuilder, AlertManager) không an toàn cho multi-process. Multiple workers sẽ tạo ra split-brain state.

---

## 9. Troubleshooting

### Backend không khởi động

```bash
# Xem logs
docker compose logs ids-backend

# Kiểm tra config
docker compose exec ids-backend python -c "from backend.config import get_settings; print(get_settings())"
```

**Lỗi thường gặp:**
- `[PRODUCTION] Startup blocked — insecure configuration` → Cập nhật `API_KEY` và `SECRET_KEY` trong `.env`
- `[PRODUCTION] CORS_ORIGINS is empty` → Set `CORS_ORIGINS` trong `.env`
- `Error initializing database` → PostgreSQL chưa ready, chờ thêm hoặc kiểm tra credentials

### Packet sniffer không hoạt động

```bash
# Kiểm tra interfaces có sẵn
python backend/scripts/list_interfaces.py

# Test dry run (3 giây)
curl -X POST "http://localhost:8000/api/sniffer/start?interface=eth0&dry_run=true" \
     -H "X-API-Key: your-api-key"
```

**Lỗi thường gặp:**
- `PermissionError: Npcap required` → Cài lại Npcap từ https://npcap.com/ với WinPcap API compatibility
- `Interface 'eth0' not found` → Chạy `list_interfaces.py` để xem tên đúng
- `NET_RAW capability missing` → Thêm `cap_add: [NET_RAW, NET_ADMIN]` vào docker-compose.yml

### Không có alerts

```bash
# Kiểm tra pipeline stats
curl http://localhost:8000/api/sniffer/status -H "X-API-Key: your-api-key"
# Xem: inference_runs > 0 chưa?

# Kiểm tra model loaded
curl http://localhost:8000/health/detailed
# Xem: model_loaded: true chưa?
```

**Nguyên nhân thường gặp:**
- `inference_runs = 0` → Traffic không đủ `min_packets` threshold
- `model_loaded: false` → Chạy `python backend/ml/create_dummy_models.py`
- Alerts bị suppress → Confidence < 0.75 hoặc IP đang trong cooldown

### Database connection errors

```bash
# Kiểm tra PostgreSQL
docker compose ps postgres
docker compose exec postgres pg_isready -U ids_user -d ids_db

# Kiểm tra Redis
docker compose exec redis redis-cli -a your-redis-pass ping

# Kiểm tra MongoDB
docker compose exec mongodb mongosh --username ids_mongo_user --password ids_mongo_pass --eval "db.adminCommand('ping')"
```

### Email alerts không gửi

```bash
# Kiểm tra config
grep -E "SMTP|EMAIL" .env

# Xem logs
docker compose logs ids-backend | grep -i email

# Test SMTP connection
python -c "
import asyncio, aiosmtplib
async def test():
    await aiosmtplib.connect(hostname='smtp.gmail.com', port=587, start_tls=True)
    print('SMTP OK')
asyncio.run(test())
"
```

---

## 10. Production Checklist

```
Infrastructure:
[ ] Xóa privileged: true khỏi docker-compose.yml
[ ] Chuyển tất cả credentials sang .env (gitignored)
[ ] Xóa host port mappings cho PostgreSQL, MongoDB, Redis
[ ] Thêm depends_on: condition: service_healthy
[ ] Cấu hình Nginx với TLS
[ ] Xóa ./backend bind mount (bake code vào image)

Application:
[ ] ENVIRONMENT=production
[ ] API_KEY mạnh (>= 16 chars, random)
[ ] SECRET_KEY mạnh (>= 32 chars, random)
[ ] CORS_ORIGINS chỉ chứa domain thực tế
[ ] API_RELOAD=false (hoặc không set, default là false)
[ ] Tạo models thật từ CICIDS2017 (không dùng dummy)

Database:
[ ] Backup schedule đã cấu hình
[ ] PostgreSQL authentication đã set
[ ] MongoDB authentication đã set
[ ] Redis password đã set

Monitoring:
[ ] /health/detailed trả về tất cả connected: true
[ ] Prometheus scrape đã cấu hình
[ ] Log rotation đã cấu hình
[ ] Alert khi pipeline dừng bất ngờ

Security:
[ ] API key rotation procedure đã document
[ ] .env không bị commit vào git
[ ] SSL certificate hợp lệ
[ ] Firewall rules đã cấu hình
```
