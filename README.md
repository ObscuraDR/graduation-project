# Z-Sentinel IDS — Machine Learning-based Intrusion Detection System

Hệ thống phát hiện xâm nhập mạng thời gian thực dựa trên Machine Learning.

---

## Quick Start

```bash
# 1. Clone & cài dependencies
pip install -r requirements.txt
cp .env.example .env

# 2. Tạo dummy models (cho dev/demo)
python backend/ml/create_dummy_models.py

# 3. Start databases + backend
docker compose up -d postgres
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Start frontend (terminal khác)
cd frontend && npm install && npm run dev

# 5. Mở dashboard
# http://localhost:3000
```

---

## Cấu trúc dự án

```
graduation-project/
│
├── frontend/                      ← React Dashboard application (Vite, Tailwind, Recharts)
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.js
│
├── backend/                       ← Core FastAPI Backend API & Services
│   ├── main.py                    — Entry point FastAPI application
│   ├── config.py                  — Operational configuration & settings
│   ├── alembic/                   — Database schema migration files
│   ├── api/                       — REST API endpoints & WebSocket handlers
│   ├── database/                  — PostgreSQL ORM models & data access
│   ├── detection_engine/          — Rule engine & predictor integration
│   ├── feature_engine/            — Network packet feature extractor
│   ├── flow_engine/               — 5-tuple flow aggregator
│   ├── alert_engine/              — Real-time alert processing
│   ├── pipeline/                  — Real-time data processing pipeline
│   ├── notifications/             — Multi-channel notifications (SMTP, Discord, Telegram)
│   ├── monitoring/                — Metrics & health checks
│   └── tests/                     — Pytest test suite
│
├── ai/                            ← AI & Machine Learning Module
│   ├── models.py                  — Model architectures (RandomForest, XGBoost, Ensemble)
│   ├── lstm_model.py              — Sequential LSTM model architecture
│   ├── inference.py               — Real-time ML inference pipeline
│   ├── training.py                — Model training pipeline
│   ├── train_flow_model.py        — Flow-level model training entrypoint
│   ├── xai.py                     — Explainable AI engine (SHAP / LIME explanations)
│   ├── create_dummy_models.py     — Model initialization utility
│   └── generate_training_data.py  — Synthetic training data generation
│
├── data/                          ← Datasets & Data Storage
│   ├── raw/                       — Raw traffic datasets (CICIDS2017)
│   ├── processed/                 — Preprocessed datasets (cicids2017_processed.csv)
│   ├── geoip/                     — MaxMind GeoIP database (GeoLite2-Country.mmdb)
│   └── models/                    — Trained model binary artifacts (.pkl, .h5)
│
├── docs/                          ← Project Documentation
│   ├── architecture/              — Architectural guides & database consolidation notes
│   ├── setup/                     — Migration guides & environment configuration
│   └── checklists/                — System verification & demo checklists
│
├── scripts/                       ← Utility & Automation Scripts
│   ├── startup/                   — Startup scripts (run_local.ps1, start.ps1, start.sh)
│   ├── demo/                      — Attack & firewall demo scripts
│   ├── db/                        — Database indexing & maintenance scripts
│   └── verification/              — Log & alert bridge verification scripts
│
├── docker-compose.yml             — PostgreSQL + Backend + Dashboard + Nginx orchestration
├── Dockerfile                     — Backend container image build configuration
├── entrypoint.sh                  — Container initialization & startup script
├── requirements.txt               — Python package dependencies
├── pytest.ini                     — Test suite configuration
├── .env.example                   — System environment variables template
└── README.md                      — Project overview and quickstart guide
```

**Nguyên tắc tổ chức:**

- `frontend/`: Giao diện React Dashboard (Vite, TailwindCSS, Recharts).
- `backend/`: Core REST API Server, WebSocket, Database, Alert & Capture Engine.
- `ai/`: Các mô hình Machine Learning, Deep Learning, Inference Pipeline & XAI.
- `data/`: Lưu trữ dữ liệu huấn luyện (raw, processed) và cơ sở dữ liệu GeoIP.
- `docs/`: Tập trung toàn bộ tài liệu kiến trúc, hướng dẫn triển khai và checklist.
- `scripts/`: Chứa kịch bản tự động hóa khởi chạy, kiểm thử và demo hệ thống.
- `docs/` chứa **TẤT CẢ** tài liệu (Markdown)
- Root chỉ chứa orchestration files (Docker, configs, README)

---

## Tài liệu chính

| Tài liệu                      | Đường dẫn                                                                                                  | Khi nào đọc                              |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| **Engineering Rebuild Guide** | [`docs/ENGINEERING_REBUILD_GUIDE.md`](docs/ENGINEERING_REBUILD_GUIDE.md)                                   | Hiểu sâu kiến trúc, debug bugs, refactor |
| API Documentation             | [`docs/api/API_DOCUMENTATION.md`](docs/api/API_DOCUMENTATION.md)                                           | Tích hợp hoặc test API                   |
| Commands                      | [`docs/operations/COMMANDS.md`](docs/operations/COMMANDS.md)                                               | Tra cứu lệnh nhanh                       |
| Deployment                    | [`docs/operations/DEPLOYMENT_GUIDE.md`](docs/operations/DEPLOYMENT_GUIDE.md)                               | Deploy production                        |
| Demo Checklist                | [`docs/thesis_reports/FINAL_DEMO_CHECKLIST.md`](docs/thesis_reports/FINAL_DEMO_CHECKLIST.md)               | Buổi bảo vệ luận văn                     |
| Training Guide                | [`docs/machine_learning/CICIDS2017_TRAINING_GUIDE.md`](docs/machine_learning/CICIDS2017_TRAINING_GUIDE.md) | Train model từ CICIDS2017                |

---

## Tech Stack

| Component      | Technology                                  |
| -------------- | ------------------------------------------- |
| Backend        | FastAPI 0.104 + Uvicorn (Python 3.10+)      |
| Frontend       | React 18 + Vite + TailwindCSS + Recharts    |
| ML             | scikit-learn, XGBoost, SHAP                 |
| Databases      | PostgreSQL 14                               |
| Packet Capture | Scapy (Npcap on Windows / libpcap on Linux) |
| Deployment     | Docker Compose                              |

---

## API Endpoints (tóm tắt)

| Method | Endpoint              | Mô tả              | Auth |
| ------ | --------------------- | ------------------ | ---- |
| POST   | `/api/sniffer/start`  | Start IDS pipeline | ✅   |
| POST   | `/api/sniffer/stop`   | Stop pipeline      | ✅   |
| GET    | `/api/sniffer/status` | Pipeline stats     | ✅   |
| GET    | `/api/traffic/stats`  | Traffic monitoring | ❌   |
| GET    | `/api/alerts/`        | List alerts        | ❌   |
| POST   | `/api/xai/explain`    | SHAP explanation   | ❌   |
| GET    | `/health/detailed`    | Service health     | ❌   |
| WS     | `/ws`                 | Real-time alerts   | ❌   |

---

## Common Commands

```bash
# Development
pip install -r requirements.txt
python backend/ml/create_dummy_models.py
python -m uvicorn backend.main:app --reload

# Testing
pytest backend/tests/ -v
pytest backend/tests/ --cov=backend

# Validate ML feature contract
python backend/scripts/validate_features.py

# Run sniffer standalone
python backend/scripts/run_sniffer.py --interface eth0

# Train from CICIDS2017
python backend/scripts/preprocess_cicids2017.py --input-dir backend/data/cicids2017
python backend/ml/train_flow_model.py --data backend/data/cicids2017_processed.csv

# Docker
docker compose up -d
docker compose logs -f ids-backend
docker compose down

# Frontend
cd frontend
npm install
npm run dev      # Development
npm run build    # Production
```

---

## License

Graduation project — academic purposes.
