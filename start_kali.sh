#!/bin/bash
# ============================================================================
#  Z-Sentinel IDS — Kali Linux Start Script
#  Cách dùng: sudo ./start_kali.sh
#  Tùy chọn : sudo ./start_kali.sh stop   → dừng tất cả
#             sudo ./start_kali.sh attack  → chạy demo tấn công
# ============================================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/.venv/bin/activate"
LOG_DIR="$PROJECT_DIR/logs"
ACTION="${1:-start}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

mkdir -p "$LOG_DIR"

print_header() {
    clear
    echo -e "${CYAN}============================================================${NC}"
    echo -e "${CYAN}   Z-SENTINEL IDS — KALI LAUNCHER                          ${NC}"
    echo -e "${CYAN}============================================================${NC}"
    echo ""
}

# ── STOP ─────────────────────────────────────────────────────────────────────
if [ "$ACTION" = "stop" ]; then
    print_header
    echo -e "${YELLOW}[>>] Dang dung tat ca services...${NC}"
    pkill -f "uvicorn backend.main" 2>/dev/null && echo -e "${GREEN}  [OK] Backend da dung${NC}"
    pkill -f "vite" 2>/dev/null && echo -e "${GREEN}  [OK] Frontend da dung${NC}"
    pkill -f "agent.py" 2>/dev/null && echo -e "${GREEN}  [OK] Agent da dung${NC}"
    echo ""
    echo -e "${GREEN}  Tat ca services da dung.${NC}"
    exit 0
fi

# ── ATTACK DEMO ──────────────────────────────────────────────────────────────
if [ "$ACTION" = "attack" ]; then
    print_header
    echo -e "${RED}[DEMO] Bat dau tan cong...${NC}"
    echo ""

    # SSH Brute Force log
    echo -e "${YELLOW}[1/2] Tao SSH brute force log...${NC}"
    for i in {1..20}; do
        echo "$(date '+%b %d %H:%M:%S') kali sshd[1234]: Failed password for root from 203.113.45.22 port $((RANDOM % 60000)) ssh2" >> /var/log/auth.log
        sleep 0.3
    done
    echo -e "${GREEN}  [OK] Da tao 20 dong SSH fail${NC}"

    # Inject alerts để trigger auto-block
    echo -e "${YELLOW}[2/2] Inject alerts de trigger auto-block...${NC}"
    for i in $(seq 1 12); do
        curl -s -X POST http://localhost:8000/api/alerts/ \
            -H 'Content-Type: application/json' \
            -H 'X-API-Key: changeme-set-API_KEY-in-env' \
            -d '{"src_ip":"203.113.45.22","dst_ip":"127.0.0.1","attack_type":"BruteForce","severity":"high","confidence":0.92,"alert_id":"demo-'$i'-'$RANDOM'","timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > /dev/null
        echo -n "."
        sleep 0.3
    done
    echo ""
    echo -e "${GREEN}  [OK] IP 203.113.45.22 da bi chan tren Firewall!${NC}"
    echo ""
    echo -e "${CYAN}  Kiem tra: http://localhost:3000/firewall${NC}"
    exit 0
fi

# ── START ─────────────────────────────────────────────────────────────────────
print_header

# Kiểm tra venv
if [ ! -f "$VENV" ]; then
    echo -e "${RED}[ERR] Chua cai dat. Chay: sudo ./setup_kali.sh${NC}"
    exit 1
fi

# ── Bước 1: PostgreSQL ───────────────────────────────────────────────────────
echo -e "${YELLOW}[1/4] Khoi dong PostgreSQL...${NC}"
service postgresql start 2>/dev/null || systemctl start postgresql 2>/dev/null || true
sleep 1
if pg_isready -U ids_user -d ids_db -q 2>/dev/null; then
    echo -e "${GREEN}  [OK] PostgreSQL dang chay${NC}"
else
    echo -e "${YELLOW}  [!!] PostgreSQL co the chua san sang, tiep tuc...${NC}"
fi

# ── Bước 2: Backend ──────────────────────────────────────────────────────────
echo -e "${YELLOW}[2/4] Khoi dong Backend (FastAPI)...${NC}"
cd "$PROJECT_DIR"
source "$VENV"

# Chạy migration
alembic upgrade head >> "$LOG_DIR/setup.log" 2>&1 || true

# Khởi động backend trong background
nohup python -m uvicorn backend.main:app \
    --host 0.0.0.0 --port 8000 --reload \
    > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$LOG_DIR/backend.pid"

# Chờ backend sẵn sàng
echo -n "  Dang cho backend..."
for i in $(seq 1 15); do
    sleep 2
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}  [OK] Backend dang chay tai: http://localhost:8000${NC}"
        break
    fi
    echo -n "."
done

# ── Bước 3: Frontend ─────────────────────────────────────────────────────────
echo -e "${YELLOW}[3/4] Khoi dong Frontend (React)...${NC}"
cd "$PROJECT_DIR/frontend"
nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$LOG_DIR/frontend.pid"
sleep 3
echo -e "${GREEN}  [OK] Frontend dang chay tai: http://localhost:3000${NC}"

# ── Bước 4: Agent ────────────────────────────────────────────────────────────
echo -e "${YELLOW}[4/4] Khoi dong Agent...${NC}"
cd "$PROJECT_DIR"
source "$VENV"
export IDS_API_URL="http://localhost:8000/api/servers"
export AGENT_API_KEY="changeme-set-API_KEY-in-env"
export AGENT_SSL_VERIFY="false"
nohup python backend/scripts/agent.py \
    > "$LOG_DIR/agent.log" 2>&1 &
AGENT_PID=$!
echo $AGENT_PID > "$LOG_DIR/agent.pid"
sleep 2
echo -e "${GREEN}  [OK] Agent dang chay${NC}"

# ── Tóm tắt ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  He thong da khoi dong thanh cong!                         ${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "  Dashboard  : ${CYAN}http://localhost:3000${NC}"
echo -e "  API Docs   : ${CYAN}http://localhost:8000/docs${NC}"
echo -e "  Dang nhap  : ${CYAN}admin / admin123${NC}"
echo ""
echo -e "  Xem log    : ${YELLOW}tail -f $LOG_DIR/backend.log${NC}"
echo -e "  Demo tan cong: ${YELLOW}sudo ./start_kali.sh attack${NC}"
echo -e "  Dung he thong: ${YELLOW}sudo ./start_kali.sh stop${NC}"
echo ""
echo -e "${CYAN}  Nhan Ctrl+C de thoat (he thong van chay background)${NC}"
echo ""

# Giữ terminal và hiển thị log realtime
tail -f "$LOG_DIR/backend.log" "$LOG_DIR/agent.log" 2>/dev/null
