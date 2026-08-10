#!/bin/bash
# ============================================================================
#  Z-Sentinel IDS — Kali Linux Setup Script
#  Chạy một lần để cài đặt toàn bộ dependencies
#  Cách dùng: chmod +x setup_kali.sh && sudo ./setup_kali.sh
# ============================================================================

set -e  # Dừng nếu có lỗi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}   Z-SENTINEL IDS — KALI SETUP                             ${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# ── Bước 1: Cài system packages ──────────────────────────────────────────────
echo -e "${YELLOW}[1/6] Cai dat system packages...${NC}"
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    postgresql postgresql-client libpq-dev \
    nodejs npm \
    nmap hping3 \
    curl wget git 2>/dev/null || true
echo -e "${GREEN}  [OK] System packages da cai xong${NC}"

# ── Bước 2: Cài Node.js mới nếu cần ─────────────────────────────────────────
echo -e "${YELLOW}[2/6] Kiem tra Node.js...${NC}"
NODE_VER=$(node -v 2>/dev/null | cut -d'v' -f2 | cut -d'.' -f1)
if [ -z "$NODE_VER" ] || [ "$NODE_VER" -lt 18 ]; then
    echo -e "${YELLOW}  Cai Node.js 20...${NC}"
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - 2>/dev/null
    apt-get install -y nodejs 2>/dev/null
fi
echo -e "${GREEN}  [OK] Node.js: $(node -v)${NC}"

# ── Bước 3: Setup PostgreSQL ─────────────────────────────────────────────────
echo -e "${YELLOW}[3/6] Cau hinh PostgreSQL...${NC}"
service postgresql start 2>/dev/null || systemctl start postgresql 2>/dev/null || true
sleep 2

# Tạo user và database
sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename='ids_user'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ids_user WITH PASSWORD 'ids_password';" 2>/dev/null || true

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='ids_db'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE ids_db OWNER ids_user;" 2>/dev/null || true

echo -e "${GREEN}  [OK] PostgreSQL da cau hinh xong${NC}"

# ── Bước 4: Tạo Python venv và cài packages ──────────────────────────────────
echo -e "${YELLOW}[4/6] Cai Python packages...${NC}"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install shap==0.52.0 --only-binary=:all: -q
pip install alembic -q
echo -e "${GREEN}  [OK] Python packages da cai xong${NC}"

# ── Bước 5: Cài frontend packages ────────────────────────────────────────────
echo -e "${YELLOW}[5/6] Cai Frontend packages...${NC}"
cd "$PROJECT_DIR/frontend"
npm install --silent 2>/dev/null
cd "$PROJECT_DIR"
echo -e "${GREEN}  [OK] Frontend packages da cai xong${NC}"

# ── Bước 6: Init database ────────────────────────────────────────────────────
echo -e "${YELLOW}[6/6] Khoi tao database...${NC}"
source .venv/bin/activate
alembic upgrade head 2>/dev/null || true
python backend/database/init_db.py 2>/dev/null || true

# Tạo dummy models nếu chưa có
if [ ! -f "backend/models/ensemble.pkl" ]; then
    echo -e "${YELLOW}  Tao dummy ML models...${NC}"
    python backend/ml/create_dummy_models.py 2>/dev/null || true
fi
echo -e "${GREEN}  [OK] Database da khoi tao xong${NC}"

# ── Tạo logs directory ───────────────────────────────────────────────────────
mkdir -p "$PROJECT_DIR/logs"

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Setup hoan tat!                                           ${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "  Chay project: ${CYAN}sudo ./start_kali.sh${NC}"
echo ""
