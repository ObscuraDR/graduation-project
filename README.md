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
z-sentinel-ids/
│
├── backend/                       ← Toàn bộ Python backend + ML
│   ├── main.py                    — FastAPI entry point
│   ├── config.py                  — Settings & env vars
│   ├── alembic/                   — Database migrations (Alembic)
│   ├── pipeline/                  — Pipeline coordinator (orchestration)
│   ├── capture_engine/            — Packet capture (Scapy)
│   ├── flow_engine/               — Flow aggregation (5-tuple)
│   ├── feature_engine/            — Feature extraction (20 features)
│   ├── detection_engine/          — ML inference + model loading
│   ├── alert_engine/              — Alert generation & correlation
│   ├── api/                       — HTTP routes, WebSocket, middleware
│   ├── database/                  — PostgreSQL, MongoDB, Redis clients
│   ├── cache/                     — Redis cache wrapper
│   ├── notifications/             — Email service (SMTP)
│   ├── monitoring/                — Prometheus metrics
│   ├── ml/                        — ML training & XAI scripts
│   ├── tests/                     — Pytest test suite
│   ├── models/                    — ML artifacts (.pkl, features.json)
│   ├── data/                      — Training data (CICIDS2017)
│   ├── reports/                   — Generated training reports
│   ├── scripts/                   — Utility scripts (validate, train, demo)
│   └── loadtests/                 — Locust load tests
│
├── frontend/                      ← React dashboard
│   ├── src/
│   │   ├── pages/                 — Overview, Alerts, Traffic, Network, AI Insights, Settings
│   │   ├── components/            — Layout, StatCard, SeverityBadge, AlertDetailModal, ConfusionMatrix
│   │   └── lib/                   — API client, WebSocket client
│   ├── package.json
│   ├── Dockerfile                 — Multi-stage build (node → nginx)
│   └── nginx.conf                 — SPA routing + API proxy
│
├── docs/                          ← Toàn bộ tài liệu
│   ├── README.md                  — Index/mục lục
│   ├── ENGINEERING_REBUILD_GUIDE.md  — ⭐ Guide chính (135KB)
│   ├── api/                       — API documentation
│   ├── architecture/              — Architecture, features, security
│   ├── machine_learning/          — ML pipeline, training guide
│   ├── operations/                — Commands, deployment, troubleshooting
│   └── thesis_reports/            — Audit, demo checklist, slides
│
├── logs/                          ← Runtime logs (gitignored)
│
├── docker-compose.yml             — PostgreSQL + MongoDB + Redis + Backend + Dashboard + Nginx
├── Dockerfile                     — Backend image
├── requirements.txt               — Python dependencies
├── pytest.ini                     — Test configuration
├── .env.example                   — Environment template
├── .gitignore
└── README.md                      — File này
```

**Nguyên tắc tổ chức:**
- `backend/` chứa **TẤT CẢ** Python code, ML artifacts, data, scripts liên quan đến backend
- `frontend/` chứa **TẤT CẢ** React code, không tương tác trực tiếp với filesystem backend
- `docs/` chứa **TẤT CẢ** tài liệu (Markdown)
- Root chỉ chứa orchestration files (Docker, configs, README)

---

## Tài liệu chính

| Tài liệu | Đường dẫn | Khi nào đọc |
|---|---|---|
| **Engineering Rebuild Guide** | [`docs/ENGINEERING_REBUILD_GUIDE.md`](docs/ENGINEERING_REBUILD_GUIDE.md) | Hiểu sâu kiến trúc, debug bugs, refactor |
| API Documentation | [`docs/api/API_DOCUMENTATION.md`](docs/api/API_DOCUMENTATION.md) | Tích hợp hoặc test API |
| Commands | [`docs/operations/COMMANDS.md`](docs/operations/COMMANDS.md) | Tra cứu lệnh nhanh |
| Deployment | [`docs/operations/DEPLOYMENT_GUIDE.md`](docs/operations/DEPLOYMENT_GUIDE.md) | Deploy production |
| Demo Checklist | [`docs/thesis_reports/FINAL_DEMO_CHECKLIST.md`](docs/thesis_reports/FINAL_DEMO_CHECKLIST.md) | Buổi bảo vệ luận văn |
| Training Guide | [`docs/machine_learning/CICIDS2017_TRAINING_GUIDE.md`](docs/machine_learning/CICIDS2017_TRAINING_GUIDE.md) | Train model từ CICIDS2017 |

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI 0.104 + Uvicorn (Python 3.10+) |
| Frontend | React 18 + Vite + TailwindCSS + Recharts |
| ML | scikit-learn, XGBoost, SHAP |
| Databases | PostgreSQL 14, MongoDB 6, Redis 7 |
| Packet Capture | Scapy (Npcap on Windows / libpcap on Linux) |
| Deployment | Docker Compose |

---

## API Endpoints (tóm tắt)

| Method | Endpoint | Mô tả | Auth |
|---|---|---|---|
| POST | `/api/sniffer/start` | Start IDS pipeline | ✅ |
| POST | `/api/sniffer/stop` | Stop pipeline | ✅ |
| GET | `/api/sniffer/status` | Pipeline stats | ✅ |
| GET | `/api/traffic/stats` | Traffic monitoring | ❌ |
| GET | `/api/alerts/` | List alerts | ❌ |
| POST | `/api/xai/explain` | SHAP explanation | ❌ |
| GET | `/health/detailed` | Service health | ❌ |
| WS | `/ws` | Real-time alerts | ❌ |

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
