#!/bin/bash
# ============================================================
# Z-Sentinel IDS — Startup Script cho Linux/Kali VM
# Cách dùng: chmod +x start.sh && ./start.sh
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

echo -e "${CYAN}"
echo "==================================================="
echo "  Z-Sentinel IDS — Starting on Linux/Kali"
echo "==================================================="
echo -e "${NC}"

# ──────────────────────────────────────────────────────────
# BƯỚC 1: Kiểm tra dependencies
# ──────────────────────────────────────────────────────────
echo -e "${YELLOW}[1/7] Checking dependencies...${NC}"

command -v python3 >/dev/null || {
    echo -e "${RED}ERROR: python3 not found.${NC}"
    echo "  Run: sudo apt install python3 python3-pip -y"
    exit 1
}

command -v node >/dev/null || {
    echo -e "${RED}ERROR: node not found.${NC}"
    echo "  Run: sudo apt install nodejs npm -y"
    exit 1
}

# Kiểm tra Docker (nếu không có → dùng PostgreSQL system)
if ! command -v docker >/dev/null 2>&1; then
    echo -e "${YELLOW}  WARNING: docker not found. Will try system PostgreSQL.${NC}"
    USE_SYSTEM_PG=1
else
    USE_SYSTEM_PG=0
fi

echo -e "${GREEN}  OK${NC}"

# ──────────────────────────────────────────────────────────
# BƯỚC 2: Tạo .env nếu chưa có
# ──────────────────────────────────────────────────────────
echo -e "${YELLOW}[2/7] Setting up .env...${NC}"

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}  Created .env from .env.example${NC}"
    else
        echo -e "${RED}ERROR: .env.example not found!${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}  .env exists, skipping${NC}"
fi

# Tự động điền KALI_IP vào CORS_ORIGINS nếu chưa có
KALI_IP=$(hostname -I | awk '{print $1}')
if [ -n "$KALI_IP" ]; then
    if ! grep -q "$KALI_IP" .env 2>/dev/null; then
        # Thêm IP vào CORS_ORIGINS
        sed -i "s|CORS_ORIGINS=.*|CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://${KALI_IP}:3000|g" .env
        echo -e "${GREEN}  Auto-added Kali IP ${KALI_IP} to CORS_ORIGINS${NC}"
    fi
fi

# ──────────────────────────────────────────────────────────
# BƯỚC 3: Tạo logs folder
# ──────────────────────────────────────────────────────────
echo -e "${YELLOW}[3/7] Creating folders...${NC}"
mkdir -p logs backend/models
echo -e "${GREEN}  OK${NC}"

# ──────────────────────────────────────────────────────────
# BƯỚC 4: Khởi động PostgreSQL
# ──────────────────────────────────────────────────────────
echo -e "${YELLOW}[4/7] Starting PostgreSQL...${NC}"

if [ "$USE_SYSTEM_PG" -eq 1 ]; then
    # Dùng PostgreSQL đã cài trên hệ thống
    echo "  Using system PostgreSQL..."
    sudo systemctl start postgresql 2>/dev/null || sudo service postgresql start 2>/dev/null || true
    
    # Tạo DB và user nếu chưa có
    sudo -u postgres psql -c "CREATE USER ids_user WITH PASSWORD 'ids_password';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE ids_db OWNER ids_user;" 2>/dev/null || true
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ids_db TO ids_user;" 2>/dev/null || true
    
    echo -e "${GREEN}  System PostgreSQL ready${NC}"
else
    # Dùng Docker
    echo "  Using Docker PostgreSQL..."
    docker compose up -d postgres
    
    echo -n "  Waiting for PostgreSQL to be healthy"
    for i in $(seq 1 15); do
        if docker compose exec -T postgres pg_isready -U ids_user -d ids_db >/dev/null 2>&1; then
            echo -e " ${GREEN}OK${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
fi

# ──────────────────────────────────────────────────────────
# BƯỚC 5: Cài Python packages
# ──────────────────────────────────────────────────────────
echo -e "${YELLOW}[5/7] Installing Python packages...${NC}"

# Dùng pip3 hoặc pip trong venv
PIP_CMD="pip3"
if [ -f ".venv/bin/pip" ]; then
    PIP_CMD=".venv/bin/pip"
fi

$PIP_CMD install -r requirements.txt -q --no-warn-script-location
echo -e "${GREEN}  OK${NC}"

# ──────────────────────────────────────────────────────────
# BƯỚC 6: Tạo ML models nếu chưa có
# ──────────────────────────────────────────────────────────
echo -e "${YELLOW}[6/7] Checking ML models...${NC}"

if [ ! -f backend/models/ensemble.pkl ]; then
    echo "  Creating dummy ML models..."
    python3 backend/ml/create_dummy_models.py
    echo -e "${GREEN}  OK — dummy models created${NC}"
else
    echo -e "${GREEN}  Models exist, skipping${NC}"
fi

# ──────────────────────────────────────────────────────────
# BƯỚC 7: Cài Node packages nếu chưa có
# ──────────────────────────────────────────────────────────
echo -e "${YELLOW}[7/7] Checking Node packages...${NC}"

if [ ! -d frontend/node_modules ]; then
    echo "  Installing Node packages (may take a minute)..."
    cd frontend && npm install --silent && cd ..
    echo -e "${GREEN}  OK${NC}"
else
    echo -e "${GREEN}  Node packages exist, skipping${NC}"
fi

# ──────────────────────────────────────────────────────────
# XONG — In hướng dẫn
# ──────────────────────────────────────────────────────────

# Lấy IP thực của Kali để hiển thị
KALI_IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${CYAN}==================================================="
echo "  SETUP COMPLETE!"
echo "==================================================="
echo -e "${NC}"
echo "  Kali VM IP: ${KALI_IP}"
echo ""
echo -e "${YELLOW}  Mở 2 terminal riêng và chạy lần lượt:${NC}"
echo ""
echo -e "${GREEN}  Terminal 1 — Backend:${NC}"
echo "    python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo -e "${GREEN}  Terminal 2 — Frontend:${NC}"
echo "    cd frontend && npm run dev -- --host 0.0.0.0"
echo ""
echo -e "${YELLOW}  Truy cập Dashboard:${NC}"
echo "    Từ Kali VM:     http://localhost:3000"
echo "    Từ Windows host: http://${KALI_IP}:3000"
echo ""
echo -e "${YELLOW}  Login mặc định:${NC} admin / admin123"
echo ""
echo -e "${YELLOW}  Demo tấn công:${NC}"
echo "    python3 backend/scripts/simulate_attack.py --type DDoS"
echo "    python3 backend/scripts/simulate_attack.py --type PortScan"
echo ""
echo -e "${YELLOW}  Chạy Agent trên máy chủ con:${NC}"
echo "    AGENT_SERVER_ID=1 \\"
echo "    AGENT_API_KEY=changeme-set-API_KEY-in-env \\"
echo "    IDS_API_URL=http://${KALI_IP}:8000/api/servers \\"
echo "    python3 backend/scripts/agent.py"
echo -e "${CYAN}===================================================${NC}"
