# Checklist Demo Firewall Auto-block

## 1. Cấu hình .env (BẮT BUỘC)

Copy từ `.env.example` và chỉnh sửa các biến sau:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ids_db
POSTGRES_USER=ids_user
POSTGRES_PASSWORD=ids_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# API
API_KEY=changeme  # Dùng cái này cho demo
SECRET_KEY=your-secret-key-change-this-in-production

# Environment
ENVIRONMENT=development

# CORS (cho development có thể để trống, sẽ default localhost:3000)
CORS_ORIGINS=

# Demo replay (tùy chọn)
ENABLE_DEMO_REPLAY=true

# Email alerts (tắt cho demo)
ENABLE_EMAIL_ALERTS=false
```

## 2. Khởi động Database

### PostgreSQL (BẮT BUỘC)
```bash
# Dùng Docker
docker-compose up -d postgres

# Hoặc PostgreSQL local
# Đảm bảo PostgreSQL đang chạy trên localhost:5432
```

### Redis (KHÔNG CẦN)
- Project dùng In-Memory Cache thay vì Redis thật
- Không cần khởi động Redis

## 3. Khởi động Backend

```bash
# Từ thư mục gốc project
python backend/main.py
```

**Kiểm tra log:**
- ✅ "Database initialized successfully"
- ✅ "Server log batch worker started"
- ✅ "Log cleanup worker started (runs every 1 hour)"
- ✅ "Application startup complete"

## 4. Test Backend Health

Mở terminal mới:
```bash
curl http://localhost:8000/health
```

Phải trả về:
```json
{
  "status": "healthy",
  "service": "IDS Backend",
  "version": "1.0.0",
  "pipeline_running": false
}
```

## 5. Chạy Demo Firewall

```powershell
# Từ thư mục gốc project
.\demo_firewall.ps1
```

**Kết quả mong đợi:**
- ✅ Backend healthy
- ✅ Test server created/exists
- ✅ 25 events sent
- ✅ IP 192.168.1.100 BLOCKED
- ✅ Security logs found

## 6. Kiểm tra Backend Logs

Trong terminal backend, bạn sẽ thấy:
```
[DEBUG] AlertManager triggered for ssh_brute_force from 192.168.1.100
[WARNING] Auto-blocking 192.168.1.100: 25 alerts in 60s
[INFO] Auto-blocked IP 192.168.1.100 added to blacklist
```

## 7. Kiểm tra qua API

```bash
# Kiểm tra blacklist
curl http://localhost:8000/api/blacklist

# Kiểm tra logs
curl http://localhost:8000/api/logs?source_ip=192.168.1.100
```

## 8. (Tùy chọn) Demo với Agent thật

Nếu muốn demo với agent thật:

### 8.1 Tạo server trong DB
```bash
curl -X POST http://localhost:8000/api/servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "agent-server-1",
    "ip_address": "192.168.1.50",
    "os": "Linux",
    "description": "Test server for agent demo"
  }'
```

### 8.2 Tạo file log giả cho agent
```bash
# Tạo file với 25+ failed SSH
cat > /tmp/agent_auth.log << 'EOF'
Jun 29 10:00:00 sshd[1234]: Failed password from 192.168.1.100
... (25 dòng)
EOF
```

### 8.3 Chạy agent
```bash
export AGENT_SERVER_ID=2  # ID của server vừa tạo
export AGENT_API_KEY=changeme
export IDS_API_URL=http://localhost:8000/api/servers
export AGENT_LOG_PATH=/tmp/agent_auth.log
export AGENT_SSL_VERIFY=false

python backend/scripts/agent.py
```

Agent sẽ:
- Đọc file log mỗi 30s
- Phát hiện SSH brute force
- Gửi batch events về backend
- Backend trigger AlertManager → auto-block

## Xử lý lỗi thường gặp

### Lỗi: "Backend is not running"
→ Khởi động backend: `python backend/main.py`

### Lỗi: "Database connection failed"
→ Kiểm tra PostgreSQL đang chạy: `docker ps` hoặc `pg_isready`

### Lỗi: "Redis connection failed"
→ Kiểm tra Redis đang chạy: `redis-cli ping`

### Lỗi: "Failed to send events: 401"
→ Kiểm tra API_KEY trong script demo khớp với .env

### Lỗi: "IP not blocked"
→ Kiểm tra backend logs xem AlertManager có lỗi không
→ Có thể cần tăng số events (hiện tại 25, ngưỡng auto-block là 10 alerts trong 60s)

## Tóm tắt flow demo

```
1. Cấu hình .env
2. Khởi động PostgreSQL + Redis
3. Khởi động Backend
4. Chạy demo_firewall.ps1
5. Kiểm tra IP bị block trong blacklist
6. Kiểm tra security logs
```
