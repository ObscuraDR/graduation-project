# SLIDE OUTLINE
## Machine Learning-Based Intrusion Detection System (IDS)
### Graduation Thesis Defense Presentation

**Recommended total slides:** 18  
**Recommended duration:** 20–25 minutes presentation + 5-minute live demo  

---

## Slide 1 — Title Slide

**Content:**
- Title: Machine Learning-Based Network Intrusion Detection System
- Subtitle: Real-Time Traffic Analysis with Explainable AI
- Author name, student ID, department
- Supervisor name
- Date

**Speaker notes:**
> "Good [morning/afternoon]. Today I will present my graduation project: a real-time network intrusion detection system that uses machine learning to classify network traffic and generate security alerts. I will walk through the motivation, architecture, implementation, and a live demonstration."

---

## Slide 2 — Problem Statement

**Content:**
- Cyber attacks are increasing in frequency and sophistication
- Traditional signature-based IDS: cannot detect zero-day attacks
- Manual analysis: does not scale to modern network speeds
- Need: automated, adaptive, real-time detection

**Bullet points:**
- 2023: 72% increase in data breaches vs. 2021 (IBM Cost of a Data Breach Report)
- Signature-based systems miss ~40% of novel attacks
- Security analysts face alert fatigue from false positives
- Goal: ML-based system with low FPR and explainable decisions

**Speaker notes:**
> "The core problem is that traditional intrusion detection systems rely on known attack signatures. They cannot detect new attack variants, and they generate too many false positives. My system addresses this by learning statistical patterns from labeled network traffic data."

---

## Slide 3 — Research Objectives

**Content:**
1. Build a real-time packet capture and flow assembly pipeline
2. Train an ensemble ML model on the CICIDS2017 benchmark dataset
3. Implement an intelligent alert engine with suppression logic
4. Provide explainable AI (SHAP) for every prediction
5. Expose a secure REST API with authentication and rate limiting
6. Build a React dashboard for real-time monitoring (6 pages)
7. Validate with a comprehensive automated test suite

---

## Slide 4 — Related Work / Background

**Content:**
- CICIDS2017 dataset: industry-standard IDS benchmark (Sharafaldin et al., 2018)
- CICFlowMeter: bidirectional flow feature extraction methodology
- Random Forest for IDS: high accuracy, interpretable, handles imbalanced classes
- XGBoost: gradient boosting, strong on tabular data
- SHAP (Lundberg & Lee, 2017): model-agnostic feature attribution
- FastAPI: modern async Python web framework

**Speaker notes:**
> "My work builds on the CICIDS2017 dataset, which is the most widely cited IDS benchmark. I use the same 20 flow-level features that CICFlowMeter extracts, ensuring my results are comparable to published literature."

---

## Slide 5 — System Architecture Overview

**Content:** Architecture diagram (from `FINAL_AUDIT_REPORT.md` Section 2)

```
Network Interface
      ↓
Capture Engine (Scapy)
      ↓
Flow Engine (5-tuple flows)
      ↓
Feature Engine (20 features)
      ↓
Detection Engine (Ensemble ML)
      ↓
Alert Engine (4-gate suppression)
      ↓
PostgreSQL / WebSocket / Email
```

**Speaker notes:**
> "The system has seven layers. Packets are captured from a live network interface using Scapy, assembled into bidirectional flows, transformed into 20 statistical features, classified by the ML model, and — if an attack is detected — an alert is generated and distributed to the database, dashboard, and email."

---

## Slide 6 — Data Pipeline: Packet to Feature

**Content:**
- **Capture:** Scapy sniffs raw IP packets; extracts src/dst IP, ports, protocol, TCP flags, payload size
- **Flow assembly:** Groups packets by 5-tuple (src_ip, src_port, dst_ip, dst_port, protocol)
- **20 features computed per flow:**

| Category | Features |
|---|---|
| Volume | `total_fwd/bwd_packets`, `total_fwd/bwd_bytes` |
| Rate | `packet_rate`, `byte_rate`, `fwd/bwd_packet_rate`, `fwd/bwd_byte_rate` |
| Timing | `flow_duration`, `inter_arrival_time_mean` |
| TCP Flags | `syn_count`, `fin_count`, `rst_count`, `psh_count`, `ack_count` |
| Size | `avg_packet_size`, `packet_length_mean` |
| Diversity | `unique_dst_ports` |

**Speaker notes:**
> "The feature set is identical to the CICIDS2017 paper. This is important because it means my model can be directly compared to published results, and the features are interpretable — for example, a high SYN count with low ACK count is a classic SYN flood indicator."

---

## Slide 7 — ML Model: Training and Architecture

**Content:**
- Dataset: CICIDS2017 (preprocessed to 20 features)
- Classes: Normal, DDoS, PortScan, BruteForce, Botnet, Abnormal
- Model: Ensemble (Random Forest + XGBoost, soft voting)
- Preprocessing: StandardScaler (fit on training set only)
- Class imbalance: `class_weight="balanced"` in RandomForest
- Hyperparameters: `n_estimators=100`, `max_depth=10`, `max_features="sqrt"`
- Train/test split: 50/50, `random_state=42`

**Diagram:** Training pipeline flowchart
```
CICIDS2017 CSV → Preprocess → StandardScaler → RandomForest + XGBoost → Ensemble → Saved .pkl
```

**Speaker notes:**
> "I chose an ensemble of Random Forest and XGBoost because both are strong on tabular data, and soft voting combines their probability outputs for more robust predictions. The balanced class weight ensures the model does not ignore minority attack classes."

---

## Slide 8 — Model Evaluation Results

**Content:**
- Reference: `reports/cicids2017_training_report.json`
- Show table: Accuracy, Precision (macro), Recall (macro), F1 (macro), FPR
- Show confusion matrix heatmap (generated from report JSON)
- Highlight: low false positive rate is critical for IDS (reduces alert fatigue)

**Speaker notes:**
> "The metrics are read directly from the training report JSON file, which is generated automatically by the training pipeline. The confusion matrix shows per-class performance. The false positive rate is the most important metric for an IDS — a high FPR means security analysts waste time investigating benign traffic."

---

## Slide 9 — Alert Engine: Intelligent Suppression

**Content:**
Four-gate suppression chain (show as flowchart):

```
Prediction received
        ↓
Gate 1: attack_type == "Normal"? → Suppress
        ↓
Gate 2: confidence < 0.75? → Suppress
        ↓
Gate 3: src_ip in whitelist? → Suppress
        ↓
Gate 4: same src_ip within cooldown? → Suppress
        ↓
Generate Alert → DB + WebSocket + Email
```

- Email gate: severity ∈ {high, critical} AND confidence ≥ 0.85
- Severity mapping: critical ≥ 0.90, high ≥ 0.75, medium ≥ 0.60

**Speaker notes:**
> "The alert engine is not just a pass-through. It has four suppression gates to reduce false positives and alert fatigue. The cooldown prevents the same source IP from flooding the alert log. The whitelist allows trusted internal IPs to be excluded."

---

## Slide 10 — Explainable AI: SHAP

**Content:**
- Problem: ML models are black boxes — security analysts need to know *why* a prediction was made
- Solution: SHAP (SHapley Additive exPlanations) — assigns each feature a contribution score
- Endpoint: `POST /api/xai/explain`
- Response includes: `predicted_label`, `confidence`, `top_features` (name + value + SHAP score), `base_value`

**Example output (illustrative):**
```json
{
  "predicted_label": "DDoS",
  "confidence": 0.91,
  "top_features": [
    {"feature": "packet_rate",  "value": 1200.0, "shap_value": 0.34},
    {"feature": "syn_count",    "value": 850.0,  "shap_value": 0.28},
    {"feature": "byte_rate",    "value": 98000.0,"shap_value": 0.19}
  ]
}
```

**Speaker notes:**
> "SHAP tells us that for this DDoS prediction, the high packet rate contributed 0.34 to the decision, the high SYN count contributed 0.28, and the high byte rate contributed 0.19. This is actionable information — a security analyst can immediately see which traffic characteristics triggered the alert and decide whether to investigate or whitelist the source."

---

## Slide 11 — Security Controls

**Content:**

| Control | Implementation | Verified By |
|---|---|---|
| API Key Auth | `X-API-Key` header, 401 on failure | `test_api_security.py` |
| Rate Limiting | Sliding window per IP: 10/30/60 req per 60s | `test_rate_limiting.py` |
| Input Validation | Pydantic + custom validators; rejects injection | `test_input_validation.py` |
| Alert Suppression | 4-gate chain in AlertManager | `test_alerts.py` |

**Speaker notes:**
> "Security was a first-class concern. The API key prevents unauthorized pipeline control. Rate limiting prevents denial-of-service against the API itself. Input validation rejects shell injection attempts in interface names and IP addresses — for example, an interface name like 'eth0; rm -rf /' is rejected with HTTP 422."

---

## Slide 12 — Testing Strategy

**Content:**
- 15 test files, comprehensive coverage
- No live infrastructure required (SQLite in-memory, mocked SMTP, stubbed Scapy)
- Test pyramid:

```
         /Integration\
        / (pipeline,  \
       /  DB, email)   \
      /─────────────────\
     /   Unit Tests      \
    / (models, alerts,    \
   /  security, rate,     \
  /   validation)         \
 /───────────────────────── \
```

- Key integration test: `test_pipeline_integration.py` — drives `PipelineCoordinator.packet_callback()` with synthetic packets and verifies the full chain: Flow → Feature → Prediction → Alert → DB insert → WebSocket enqueue

**Speaker notes:**
> "The test suite is fully CI-safe. I can run all tests on any machine without PostgreSQL, Npcap, or an SMTP server. The integration tests build minimal ML artifacts in a temporary directory and use SQLite in-memory for database assertions."

---

## Slide 13 — Technology Stack

**Content:**

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Web Framework | FastAPI + Uvicorn |
| Frontend | React 18 + Vite + TailwindCSS + Recharts |
| Packet Capture | Scapy + Npcap (Windows) |
| ML | scikit-learn (RandomForest), XGBoost |
| XAI | SHAP (TreeExplainer) |
| Database | PostgreSQL (SQLAlchemy ORM), MongoDB, Redis |
| Real-time | WebSocket (FastAPI native) |
| Email | aiosmtplib (async SMTP) |
| Testing | pytest + unittest.mock |
| Deployment | Docker + Docker Compose |
| CI/CD | GitHub Actions (4 jobs) |

---

## Slide 14 — Deployment Architecture

**Content:**
- Docker Compose services: `ids-backend`, `postgres`, `mongodb`, `redis`, `dashboard`
- Environment configuration via `.env` file
- Backend API available at `http://localhost:8000`
- Frontend Dashboard at `http://localhost:3000`
- Swagger UI at `http://localhost:8000/docs`
- WebSocket at `ws://localhost:8000/ws`

**Diagram:** Docker Compose service graph

```
┌──────────────────────────────────────────────────────┐
│                Docker Compose                         │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ ids-backend  │  │ postgres │  │   dashboard   │  │
│  │ :8000        │──│ :5432    │  │   :3000       │  │
│  └──────┬───────┘  └──────────┘  └───────────────┘  │
│         │           ┌──────────┐                     │
│         ├───────────│ mongodb  │                     │
│         │           │ :27017   │                     │
│         │           └──────────┘                     │
│         │           ┌──────────┐                     │
│         └───────────│  redis   │                     │
│                     │ :6379    │                     │
│                     └──────────┘                     │
└──────────────────────────────────────────────────────┘
```

---

## Slide 15 — Live Demo Plan

**Content:** (see Section: Demo Flow Plan below)

- Title: "Live Demo — 5 Minutes"
- Steps listed as numbered checklist
- Show terminal + browser side by side

---

## Slide 16 — Attack Simulation

**Content:**
Three attack types simulated during demo:

| Attack | Tool | Command | Expected Detection |
|---|---|---|---|
| Port Scan | nmap | `nmap -sS -p 1-1000 <target>` | PortScan, high confidence |
| DDoS (SYN flood) | hping3 | `hping3 -S --flood -p 80 <target>` | DDoS, critical severity |
| Brute Force (SSH) | hydra | `hydra -l root -P wordlist.txt ssh://<target>` | BruteForce, high severity |

**Windows alternatives (no hping3):**
- Use `demo_attack_simulation.ps1` which generates synthetic high-rate TCP flows
- Or use `nmap` (available on Windows via nmap.org installer)

**Speaker notes:**
> "For the demo, I use nmap for port scanning because it is available on Windows. The system detects the scan because nmap generates many SYN packets to different destination ports in a short time — exactly the pattern the model learned from CICIDS2017 PortScan traffic. The alert appears in the database and is broadcast over WebSocket within seconds."

---

## Slide 17 — Results Summary

**Content:**
- Full pipeline implemented: capture → flow → feature → ML → alert → DB/WS/email
- React dashboard with 6 pages: Overview, Alerts, Traffic, Network, AI Insights, Settings
- 15 test files, comprehensive coverage
- Security controls verified: auth, rate limiting, input validation
- SHAP explainability for every prediction
- CICIDS2017 training pipeline with automated report generation
- Demo-ready: Docker Compose + PowerShell automation scripts

**Metrics table:** (fill from `cicids2017_training_report.json` after full training run)

| Metric | Value |
|---|---|
| Accuracy | — |
| F1 (macro) | — |
| False Positive Rate | — |
| Attack Classes | 6 |
| Features | 20 |
| Frontend Pages | 6 |
| Test Files | 15 |

---

## Slide 18 — Conclusion and Future Work

**Content:**

**Achieved:**
- Real-time IDS pipeline with ML-based classification
- React dashboard with 6 pages for monitoring and analysis
- Explainable predictions via SHAP
- Production-grade security controls
- Comprehensive test coverage
- Docker Compose deployment with CI/CD

**Future Work:**
1. Replace Scapy with libpcap/AF_PACKET for higher throughput
2. Add LSTM model for temporal sequence detection
3. Deploy on Kubernetes for horizontal scaling
4. Supplement CICIDS2017 with newer datasets (CIC-IDS-2018, UNSW-NB15)
5. Add RBAC user management and JWT authentication

**Speaker notes:**
> "In conclusion, I have built a complete, tested, and demo-ready intrusion detection system with both backend and frontend. The main limitation is Scapy's throughput ceiling, which is acceptable for a lab environment but would need to be addressed for production deployment. Thank you — I am happy to take questions."

---

## Demo Flow Plan (5 Minutes)

Run `scripts/demo_full.ps1` in one terminal and keep a browser open at `http://localhost:3000` (dashboard) and `http://localhost:8000/docs` (Swagger).

| Time | Action | Expected Output |
|---|---|---|
| 0:00 | Show `docker-compose ps` | All containers `healthy` |
| 0:30 | Show frontend dashboard at `http://localhost:3000` | Overview page with stats |
| 0:45 | Show `GET /health/detailed` in Swagger | All services connected |
| 1:00 | Show `GET /api/sniffer/status` without API key | `401 Unauthorized` |
| 1:15 | Show same request with `X-API-Key` header | `200 {"is_running": false}` |
| 1:30 | Open `wscat -c ws://localhost:8000/ws` in second terminal | WebSocket connected |
| 2:00 | `POST /api/sniffer/start?interface=<iface>&model_name=ensemble` | `{"success": true}` |
| 2:30 | Run `scripts/demo_attack_simulation.ps1` (nmap scan) | Packets captured, inference running |
| 3:00 | Show WebSocket terminal | JSON alert appears in real time |
| 3:15 | Show frontend Alerts page | Alert appears in dashboard table |
| 3:30 | `GET /api/alerts/` | Alert with attack_type, severity, confidence |
| 4:00 | `POST /api/xai/explain` with feature vector | SHAP top_features response |
| 4:15 | Show frontend AI Insights page | Training metrics and confusion matrix |
| 4:30 | `POST /api/sniffer/stop` | `{"success": true, "status": "stopped"}` |
| 5:00 | Show `pytest backend/tests/ -v` (pre-run result) | All tests passed |

---

## Attack Simulation Explanation

### nmap Port Scan
```powershell
nmap -sS -p 1-1000 192.168.1.1
```
Sends SYN packets to 1,000 ports. The IDS detects this because:
- `unique_dst_ports` spikes to ~1,000
- `syn_count` is high relative to `ack_count`
- `packet_rate` is elevated
- Pattern matches CICIDS2017 PortScan class

### hping3 SYN Flood (Linux/WSL)
```bash
hping3 -S --flood -p 80 192.168.1.1
```
Sends SYN packets at maximum rate. The IDS detects this because:
- `packet_rate` and `byte_rate` are extremely high
- `syn_count` >> `ack_count` (no three-way handshake completion)
- Pattern matches CICIDS2017 DDoS class

### hydra SSH Brute Force
```bash
hydra -l root -P /usr/share/wordlists/rockyou.txt ssh://192.168.1.1
```
Sends repeated SSH authentication attempts. The IDS detects this because:
- Many flows to `dst_port=22`
- High `packet_rate` with small `avg_packet_size` (auth packets)
- Pattern matches CICIDS2017 BruteForce class

### Windows Alternative (demo_attack_simulation.ps1)
The PowerShell script generates synthetic high-rate TCP flows using `Test-NetConnection` in a loop, simulating the statistical signature of a port scan without requiring hping3.

---

*This slide outline is intended as a guide. Adjust slide count and content based on your department's presentation requirements and time allocation.*
