#!/bin/bash
# ============================================================
# Z-Sentinel IDS — Startup Script cho Linux/Kali
# Chạy: chmod +x start.sh && ./start.sh
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "==================================================="
echo "  Z-Sentinel IDS — Starting on Linux/Kali"
echo "==================================================="

# 1. Kiểm tra dependencies
echo "[1/6] Checking dependencies..."
command -v python3 >/dev/null || { echo "ERROR: python3 not found. Run: apt install python3"; exit 1; }
command -v node    >/dev/null || { echo "ERROR: node not found. Run: apt install nodejs"; exit 1; }
command -v docker  >/dev/null || { echo "ERROR: docker not found. Run: apt install docker.io"; exit 1; }
echo "  OK"

# 2. Copy .env nếu chưa có
if [ ! -f .env ]; then
    echo "[2/6] Creating .env from .env.example..."
    cp .env.example .env
    echo "  OK — edit .env to customize settings"
else
    echo "[2/6] .env exists, skipping"
fi

# 3. Tạo ML models nếu chưa có
if [ ! -f backend/models/ensemble.pkl ]; then
    echo "[3/6] Creating ML models (dummy)..."
    python3 backend/ml/create_dummy_models.py
    echo "  OK"
else
    echo "[3/6] ML models exist, skipping"
fi

# 4. Cài Python packages
echo "[4/6] Installing Python packages..."
pip3 install -r requirements.txt -q
echo "  OK"

# 5. Cài Node packages nếu chưa có
if [ ! -d frontend/node_modules ]; then
    echo "[5/6] Installing Node packages..."
    cd frontend && npm install -q && cd ..
    echo "  OK"
else
    echo "[5/6] Node packages exist, skipping"
fi

# 6. Khởi động PostgreSQL
echo "[6/6] Starting PostgreSQL..."
docker compose up -d postgres
sleep 3

# Kiểm tra PostgreSQL
if docker compose ps postgres | grep -q "healthy\|running"; then
    echo "  PostgreSQL OK"
else
    echo "  Waiting for PostgreSQL..."
    sleep 5
fi

echo ""
echo "==================================================="
echo "  READY! Run these in separate terminals:"
echo ""
echo "  Terminal 1 (Backend):"
echo "    python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "  Terminal 2 (Frontend):"
echo "    cd frontend && npm run dev -- --host 0.0.0.0"
echo ""
echo "  Then open: http://localhost:3000"
echo "  Login: admin / admin123"
echo ""
echo "  Demo attack:"
echo "    python3 backend/scripts/simulate_attack.py --type DDoS"
echo "==================================================="
