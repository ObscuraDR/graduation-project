#!/bin/sh
# entrypoint.sh - Chờ database khởi động và chạy migrations trước khi chạy FastAPI backend
set -e

echo "Dang kiem tra ket noi database..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER"; do
  echo "Database chua san sang - dang cho 1 giay..."
  sleep 1
done

echo "Database da san sang! Chay database migrations..."
alembic upgrade head

echo "Chay khoi tao du lieu va seed data..."
python backend/database/init_db.py

# Kiem tra neu thieu ML dummy model thi tu dong tao
if [ ! -f "backend/models/ensemble.pkl" ]; then
  echo "ML models chua san sang - Dang tu dong tao dummy models..."
  python backend/ml/create_dummy_models.py
fi

echo "Khoi dong FastAPI Backend Server..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
