# team_division

# Phân Chia Công Việc — Nhóm 2 Người

### Dự án: ML-based IDS | Timeline: 12 tuần (7/5 → 29/7/2026)

---

## Phân vai trò

|  | Thành viên A | Thành viên B |
| --- | --- | --- |
| **Vai trò** | 🧠 AI/ML Engineer + Backend | 🌐 Network Engineer + Frontend |
| **Chuyên trách** | ML models, API, Database, Alert | Packet Capture, Feature Extract, Dashboard |
| **Ngôn ngữ chính** | Python (ML + FastAPI) | Python (Scapy) + React (JS) |
| **Công cụ chính** | Jupyter, Scikit-learn, XGBoost, TensorFlow, PostgreSQL | Scapy, Wireshark, React, Chart.js |

---

## Phân chia theo tuần

### TUẦN 1 (7/5 - 13/5): Research + Setup

| Task | A (AI/ML) | B (Network/FE) |
| --- | --- | --- |
| **Chung** | Cùng setup dev environment (Ubuntu, Python, Docker, Git repo) |  |
| T2-T3 | Đọc papers về ML-IDS, nghiên cứu models | Đọc papers về IDS, nghiên cứu network protocols |
| T4-T5 | Download CICIDS2017, bắt đầu EDA | Nghiên cứu Scapy, PyShark, thử capture packets |
| T6-CN | EDA notebook: thống kê, visualize dataset | Setup Wireshark, hiểu packet structure, BPF filters |

> 🎯 **Sync cuối tuần:** Review EDA + chia sẻ kiến thức
> 

---

### TUẦN 2 (14/5 - 20/5): Data + ML Baseline

| Task | A (AI/ML) | B (Network/FE) |
| --- | --- | --- |
| T2-T3 | Data cleaning, feature selection (top 20-30) | Nghiên cứu flow-based features, hiểu CICFlowMeter |
| T4-T5 | Train Random Forest + evaluate | Viết script capture packets cơ bản (Scapy) |
| T6-CN | Train XGBoost + hyperparameter tuning | Thử extract basic features từ captured packets |

> 🎯 **Sync:** A demo model results, B demo packet capture
> 

---

### TUẦN 3 (21/5 - 27/5): ML Advanced + Capture Engine

| Task | A (AI/ML) | B (Network/FE) |
| --- | --- | --- |
| T2-T3 | Build LSTM model (sequence data prep + train) | Build Packet Capture Engine (multi-thread, queue) |
| T4-T5 | Train LSTM + evaluate | Thêm BPF filters, pcap saving |
| T6 | Build Ensemble (Voting: RF + XGB + LSTM) | Test capture trên local network |
| T7-CN | Full evaluation: confusion matrix, ROC, FPR | Viết unit tests cho capture module |

> 🎯 **Milestone:** A có ensemble model, B có capture engine
> 

---

### TUẦN 4 (28/5 - 3/6): Feature Extraction

| Task | A (AI/ML) | B (Network/FE) |
| --- | --- | --- |
| T2-T3 | Chuẩn bị preprocessing pipeline (scaler, encoder) | Build Flow Manager (group packets → flows by 5-tuple) |
| T4-T5 | Save trained models (joblib/pickle), viết predict module | Extract features từ flows (mapping CICIDS2017 features) |
| T6-CN | Viết inference pipeline (load model → predict) | Test: verify extracted features match training features |

> 🎯 **Sync:** Thống nhất feature format giữa A (model input) và B (extractor output)
> 

---

### TUẦN 5 (4/6 - 10/6): E2E Pipeline

| Task | A (AI/ML) | B (Network/FE) |
| --- | --- | --- |
| **Chung** | 🔥 Cùng connect pipeline: Capture → Extract → Normalize → Predict |  |
| T2-T3 | Viết normalization layer (match training preprocessing) | Connect capture output → feature extractor |
| T4-T5 | Integrate ML predict vào pipeline | Test E2E với real traffic |
| T6-CN | **Cùng test:** simulated attacks (nmap, hping3) → verify detection |  |

> 🎯 **Milestone: 🔥 E2E pipeline working** — Cả 2 cùng verify
> 

---

### TUẦN 6 (11/6 - 17/6): Database + API

| Task | A (AI/ML) | B (Network/FE) |
| --- | --- | --- |
| T2-T3 | Setup PostgreSQL, tạo tables (SQLAlchemy) | Nghiên cứu React, chọn template dashboard |
| T4-T5 | Build FastAPI: CRUD endpoints (alerts, flows, predictions) | Setup React project, install Recharts, routing |
| T6-CN | WebSocket endpoint cho real-time streaming | Thiết kế layout dashboard (sidebar, pages) |

> 🎯 **Sync:** A demo API (Swagger docs), B demo dashboard skeleton
> 

---

### TUẦN 7 (18/6 - 24/6): Alert Engine + Dashboard Core

| Task | A (AI/ML) | B (Network/FE) |
| --- | --- | --- |
| T2-T3 | Build Alert Manager (severity, thresholds) | Overview page: KPI cards, traffic line chart |
| T4-T5 | Alert storage + status management (CRUD) | Alerts page: table + filters + severity badges |
| T6-CN | Email notification (SMTP), rate limiting | AI Insights page: model metrics, confusion matrix |

> 🎯 **Sync:** A test alerts → B hiển thị trên dashboard
> 

---

### TUẦN 8 (25/6 - 1/7): Integration + Dashboard Pages

| Task | A (AI/ML) | B (Network/FE) |
| --- | --- | --- |
| T2-T3 | Connect pipeline → DB (lưu predictions, alerts) | Traffic Analysis page (protocol distribution, top IPs) |
| T4-T5 | Connect Alert Engine → API → WebSocket | Packet Logs page (searchable table, pagination) |
| T6-CN | Logging system, error handling | WebSocket integration (live dashboard updates) |

> 🎯 **Milestone:** Backend ↔︎ Frontend connected
> 

---

### TUẦN 9 (2/7 - 8/7): Full Integration + Testing

| Task | A (AI/ML) | B (Network/FE) |
| --- | --- | --- |
| **Chung** | 🔥 Full system integration test: Capture → ML → Alert → API → Dashboard |  |
| T2-T3 | Unit tests cho ML + API + Alert modules | Unit tests cho Capture + Feature modules |
| T4-T5 | Integration tests (pytest + Docker) | Fix UI bugs, responsive design |
| T6-CN | ML evaluation trên test set (final metrics) | Settings page (threshold config, model selection) |

> 🎯 **Milestone: 🔥 Full system integrated + tested**
> 

---

### TUẦN 10 (9/7 - 15/7): Optimization + Advanced

| Task | A (AI/ML) | B (Network/FE) |
| --- | --- | --- |
| T2-T3 | Add SHAP/XAI explanations cho predictions | Performance optimization: async, batch processing |
| T4-T5 | Auto-retrain pipeline (optional) | Multi-thread capture optimization |
| T6-CN | Model optimization (reduce FPR, threshold tuning) | Stress testing (hping3), performance testing (locust) |

> 🎯 **Sync:** Review XAI output, review performance metrics
> 

---

### TUẦN 11 (16/7 - 22/7): Docker + Documentation

| Task | A (AI/ML) | B (Network/FE) |
| --- | --- | --- |
| T2-T3 | Viết Dockerfile cho backend services | Viết Dockerfile cho dashboard (nginx) |
| T4-T5 | **Cùng:** Docker Compose (6 services), test deployment |  |
| T6 | Viết API documentation | Viết User Guide |
| T7-CN | README.md, architecture docs | Screenshot dashboard, record demo video |

> 🎯 **Milestone:** Docker deployment working + docs ready
> 

---

### TUẦN 12 (23/7 - 29/7): Presentation

| Task | A (AI/ML) | B (Network/FE) |
| --- | --- | --- |
| T2 | Slides: ML Models, AI Pipeline, Results | Slides: Architecture, Network, Dashboard |
| T3 | Slides: phần chung (Intro, Conclusion) | Demo script + test demo flow |
| T4 | **Cùng:** Dry-run presentation lần 1 |  |
| T5 | Fix slides, chuẩn bị Q&A | Record video demo backup |
| T6 | **Cùng:** Dry-run presentation lần 2 (final) |  |
| T7-CN | **Buffer:** fix bugs, polish |  |

> 🎯 **Milestone: 🎓 Ready to present!**
> 

---

## Tổng Quan Phân Chia Modules

```
┌─────────────────────────────────────────────────────┐
│              THÀNH VIÊN A (AI/ML + Backend)          │
│                                                      │
│  ┌────────────────┐  ┌────────────────┐             │
│  │  ML Detection  │  │  Alert Engine  │             │
│  │  Engine        │  │                │             │
│  └────────────────┘  └────────────────┘             │
│  ┌────────────────┐  ┌────────────────┐             │
│  │  FastAPI       │  │  PostgreSQL    │             │
│  │  REST API      │  │  Database      │             │
│  └────────────────┘  └────────────────┘             │
│                                                      │
├──────────────────────┬──────────────────────────────┤
│     CHUNG (cả 2)     │                              │
│  ┌────────────────┐  │                              │
│  │  E2E Pipeline  │  │                              │
│  │  Integration   │  │                              │
│  └────────────────┘  │                              │
│  ┌────────────────┐  │                              │
│  │  Docker Deploy │  │                              │
│  └────────────────┘  │                              │
│  ┌────────────────┐  │                              │
│  │  Testing       │  │                              │
│  └────────────────┘  │                              │
├──────────────────────┴──────────────────────────────┤
│              THÀNH VIÊN B (Network + Frontend)       │
│                                                      │
│  ┌────────────────┐  ┌────────────────┐             │
│  │  Packet Capture│  │  Feature       │             │
│  │  Engine        │  │  Extraction    │             │
│  └────────────────┘  └────────────────┘             │
│  ┌────────────────┐  ┌────────────────┐             │
│  │  React         │  │  WebSocket     │             │
│  │  Dashboard     │  │  Frontend      │             │
│  └────────────────┘  └────────────────┘             │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## Khối Lượng Công Việc Ước Tính

| Thành viên | Modules phụ trách | % Workload |
| --- | --- | --- |
| **A** | ML Engine (30%) + API (15%) + DB (10%) + Alert (10%) | ~50% |
| **B** | Capture (15%) + Features (15%) + Dashboard (20%) + WebSocket (5%) | ~50% |
| **Chung** | E2E Integration + Docker + Testing + Presentation | Chia đều |

> **Tổng mỗi người:** ~15-17 giờ/tuần (tổng nhóm ~30 giờ/tuần)
> 

---

## Quy Tắc Làm Việc Nhóm

### Git Workflow

```
main (protected)
  ├── develop (integration branch)
  │     ├── feature/ml-models        (A)
  │     ├── feature/api-backend      (A)
  │     ├── feature/alert-engine     (A)
  │     ├── feature/packet-capture   (B)
  │     ├── feature/feature-extract  (B)
  │     └── feature/dashboard        (B)
  └── release/v1.0
```

### Sync Points (Bắt Buộc)

| Thời điểm | Nội dung |
| --- | --- |
| **Cuối mỗi tuần** | Demo progress cho nhau (30 phút) |
| **Tuần 4** | 🔴 Thống nhất feature format (A input = B output) |
| **Tuần 5** | 🔴 Cùng test E2E pipeline |
| **Tuần 8** | 🔴 Cùng connect API ↔︎ Dashboard |
| **Tuần 9** | 🔴 Full integration test |
| **Tuần 12** | 🔴 Dry-run presentation cùng nhau |

### Công Cụ Giao Tiếp

| Mục đích | Công cụ |
| --- | --- |
| Code | GitHub (PRs, code review) |
| Chat | Zalo / Discord |
| Task tracking | GitHub Issues / Trello |
| Docs | Google Docs (shared) |
| Sync call | Google Meet (cuối tuần) |

---

## ⚠️ Rủi Ro Khi Làm Nhóm 2 Người

| Rủi ro | Giải pháp |
| --- | --- |
| Một người bị sick/bận | Mỗi người hiểu cơ bản phần của người kia, viết docs rõ ràng |
| Feature format không khớp (A ↔︎ B) | Định nghĩa interface sớm (Tuần 4), viết test cho interface |
| Merge conflict | Mỗi người làm module riêng, sync qua develop branch |
| Tiến độ lệch nhau | Weekly sync, dùng GitHub Issues tracking |
| Không biết phần của nhau | Code review bắt buộc trước khi merge |