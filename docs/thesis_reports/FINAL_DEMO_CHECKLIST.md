# FINAL DEMO CHECKLIST
## Z-Sentinel IDS — Thesis Defense Demo

Chạy checklist này từ trên xuống trước và trong buổi bảo vệ luận văn.

**Thay `<INTERFACE>` bằng tên interface thực tế** (chạy `python backend/scripts/list_interfaces.py` để xem).  
**Thay `<API_KEY>` bằng giá trị `API_KEY` trong file `.env`.**

---

## SETUP

| # | Task | Lệnh | Kết quả mong đợi | ✓ |
|---|---|---|---|---|
| 1 | Start Docker services | `docker compose up -d` | Tất cả containers start | ☐ |
| 2 | Kiểm tra PostgreSQL healthy | `docker compose ps postgres` | State: `healthy` | ☐ |
| 3 | Kiểm tra MongoDB healthy | `docker compose ps mongodb` | State: `healthy` | ☐ |
| 4 | Kiểm tra Redis healthy | `docker compose ps redis` | State: `healthy` | ☐ |
| 5 | Kiểm tra models tồn tại | `dir models\` | `ensemble.pkl`, `ensemble_scaler.pkl`, `ensemble_encoder.pkl`, `features.json` | ☐ |
| 6 | Cài wscat (nếu chưa có) | `npm install -g wscat` | `wscat` command available | ☐ |

---

## SERVER

| # | Task | Lệnh | Kết quả mong đợi | ✓ |
|---|---|---|---|---|
| 7 | Start backend | `uvicorn backend.main:app --host 0.0.0.0 --port 8000` | "Application startup complete" trong logs | ☐ |
| 8 | Basic health check | `curl http://localhost:8000/health` | `{"status": "healthy", "version": "1.0.0"}` | ☐ |
| 9 | Detailed health check | `curl http://localhost:8000/health/detailed` | `postgres/redis/mongo: connected: true`, `model_loaded: true` | ☐ |
| 10 | Mở Swagger UI | Browser → `http://localhost:8000/docs` | Tất cả endpoint groups hiển thị | ☐ |

---

## SECURITY

| # | Task | Lệnh | Kết quả mong đợi | ✓ |
|---|---|---|---|---|
| 11 | Test thiếu API key | `curl http://localhost:8000/api/sniffer/status` | `HTTP 401` `{"detail": "Invalid or missing API key"}` | ☐ |
| 12 | Test API key đúng | `curl http://localhost:8000/api/sniffer/status -H "X-API-Key: <API_KEY>"` | `HTTP 200` `{"is_running": false, ...}` | ☐ |
| 13 | Test input validation | `curl -X POST "http://localhost:8000/api/sniffer/start?interface=eth0;rm+-rf+/" -H "X-API-Key: <API_KEY>"` | `HTTP 422` "contains invalid characters" | ☐ |
| 14 | Test rate limit (optional) | Gửi 11 requests liên tiếp đến `/api/sniffer/status` | Request thứ 11 trả về `HTTP 429` | ☐ |

---

## WEBSOCKET

| # | Task | Lệnh | Kết quả mong đợi | ✓ |
|---|---|---|---|---|
| 15 | Kết nối WebSocket | `wscat -c ws://localhost:8000/ws` | "Connected (press CTRL+C to quit)" | ☐ |
| 16 | Giữ terminal WebSocket mở | — | Terminal sẵn sàng nhận alerts | ☐ |

---

## SNIFFER PIPELINE

| # | Task | Lệnh | Kết quả mong đợi | ✓ |
|---|---|---|---|---|
| 17 | Liệt kê interfaces | `python backend/scripts/list_interfaces.py` | Danh sách interfaces, ghi nhớ tên đúng | ☐ |
| 18 | Start pipeline | `curl -X POST "http://localhost:8000/api/sniffer/start?interface=<INTERFACE>&model_name=ensemble&min_packets=10" -H "X-API-Key: <API_KEY>"` | `{"status": "success", "interface": "<INTERFACE>"}` | ☐ |
| 19 | Verify pipeline running | `curl http://localhost:8000/api/sniffer/status -H "X-API-Key: <API_KEY>"` | `{"is_running": true, "processed_packets": N}` với N > 0 | ☐ |
| 20 | Kiểm tra traffic stats | `curl http://localhost:8000/api/traffic/stats` | `active_flows` > 0 | ☐ |

---

## ATTACK SIMULATION

| # | Task | Lệnh | Kết quả mong đợi | ✓ |
|---|---|---|---|---|
| 21 | Chạy attack simulation | `.\scripts\demo_attack_simulation.ps1` | Script chạy, hiển thị attack commands | ☐ |
| 22 | Port scan (nếu có nmap) | `nmap -sS -p 1-1000 <target_ip>` | nmap output | ☐ |
| 23 | Monitor packet count | `curl http://localhost:8000/api/sniffer/status -H "X-API-Key: <API_KEY>"` | `processed_packets` tăng, `inference_runs` > 0 | ☐ |
| 24 | Quan sát WebSocket alert | Xem terminal wscat | JSON alert xuất hiện: `{"type": "alert", "data": {"attack_type": "...", "severity": "...", "confidence": 0.XX}}` | ☐ |

---

## ALERTS & DATABASE

| # | Task | Lệnh | Kết quả mong đợi | ✓ |
|---|---|---|---|---|
| 25 | Xem alerts qua API | `curl http://localhost:8000/api/alerts/` | JSON array với ít nhất 1 alert | ☐ |
| 26 | Lọc critical alerts | `curl "http://localhost:8000/api/alerts/?severity=critical"` | Chỉ hiển thị critical alerts | ☐ |
| 27 | Kiểm tra PostgreSQL | `docker exec -it ids-postgres psql -U ids_user -d ids_db -c "SELECT id, attack_type, severity, confidence, source_ip FROM attack_alerts ORDER BY timestamp DESC LIMIT 5;"` | Rows hiển thị alerts | ☐ |
| 28 | Kiểm tra traffic flows | `docker exec -it ids-postgres psql -U ids_user -d ids_db -c "SELECT id, src_ip, dst_ip, protocol, packet_count FROM traffic_flows ORDER BY id DESC LIMIT 5;"` | Rows hiển thị flows | ☐ |
| 29 | Resolve một alert | `curl -X PUT "http://localhost:8000/api/alerts/{alert_id}/resolve?notes=Demo"` | `{"message": "AttackAlert resolved successfully"}` | ☐ |

---

## EXPLAINABILITY (XAI)

| # | Task | Lệnh | Kết quả mong đợi | ✓ |
|---|---|---|---|---|
| 30 | Gọi XAI explain | `curl -X POST http://localhost:8000/api/xai/explain -H "Content-Type: application/json" -d '{"model_name":"ensemble","features":{"flow_duration":1.5,"total_fwd_packets":500,"total_bwd_packets":10,"total_fwd_bytes":50000,"total_bwd_bytes":1000,"avg_packet_size":100.0,"packet_rate":1200.0,"byte_rate":98000.0,"syn_count":450,"fin_count":2,"rst_count":5,"psh_count":10,"ack_count":50,"unique_dst_ports":1,"inter_arrival_time_mean":0.001,"fwd_packet_rate":1100.0,"bwd_packet_rate":100.0,"fwd_byte_rate":90000.0,"bwd_byte_rate":8000.0,"packet_length_mean":100.0}}'` | `{"success": true, "data": {"predicted_label": "...", "top_features": [...]}}` | ☐ |
| 31 | Verify SHAP top features | Kiểm tra response `data.top_features` | Array 5 features với `feature`, `value`, `shap_value` | ☐ |

---

## EMAIL ALERTS (nếu đã cấu hình)

| # | Task | Lệnh | Kết quả mong đợi | ✓ |
|---|---|---|---|---|
| 32 | Kiểm tra email config | `grep -E "SMTP|EMAIL" .env` | Tất cả SMTP values đã set | ☐ |
| 33 | Kiểm tra email inbox | Mở email client | Email nhận được với subject "[IDS Alert] CRITICAL/HIGH: ..." | ☐ |

---

## FRONTEND DASHBOARD

| # | Task | Lệnh | Kết quả mong đợi | ✓ |
|---|---|---|---|---|
| 33a | Start frontend (nếu chưa dùng Docker) | `cd frontend && npm install && npm run dev` | Vite dev server chạy tại `http://localhost:3000` | ☐ |
| 33b | Mở Dashboard | Browser → `http://localhost:3000` | Overview page hiển thị stats | ☐ |
| 33c | Kiểm tra Alerts page | Navigate → Alerts | Bảng alerts hiển thị, filter hoạt động | ☐ |
| 33d | Kiểm tra Traffic page | Navigate → Traffic | Traffic stats và flows hiển thị | ☐ |
| 33e | Kiểm tra AI Insights page | Navigate → AI Insights | Training metrics, confusion matrix | ☐ |
| 33f | Kiểm tra Network page | Navigate → Network | Network analysis hiển thị | ☐ |
| 33g | Kiểm tra Settings page | Navigate → Settings | Service health, pipeline control | ☐ |

---

## CLEANUP

| # | Task | Lệnh | Kết quả mong đợi | ✓ |
|---|---|---|---|---|
| 34 | Dừng pipeline | `curl -X POST http://localhost:8000/api/sniffer/stop -H "X-API-Key: <API_KEY>"` | `{"status": "success", "message": "Sniffer stopped"}` | ☐ |
| 35 | Verify pipeline stopped | `curl http://localhost:8000/api/sniffer/status -H "X-API-Key: <API_KEY>"` | `{"is_running": false}` | ☐ |

---

## TEST SUITE

| # | Task | Lệnh | Kết quả mong đợi | ✓ |
|---|---|---|---|---|
| 36 | Chạy full test suite | `pytest backend/tests/ -v` | Tất cả tests pass, không có failures | ☐ |
| 37 | Coverage report (optional) | `pytest backend/tests/ --cov=backend --cov-report=term-missing` | Coverage report hiển thị | ☐ |

---

## Quick Reference: URLs

| Resource | URL |
|---|---|
| **Frontend Dashboard** | `http://localhost:3000` |
| Health check | `http://localhost:8000/health` |
| Detailed health | `http://localhost:8000/health/detailed` |
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |
| WebSocket | `ws://localhost:8000/ws` |
| Sniffer status | `http://localhost:8000/api/sniffer/status` |
| Alerts | `http://localhost:8000/api/alerts/` |
| Traffic stats | `http://localhost:8000/api/traffic/stats` |
| XAI explain | `http://localhost:8000/api/xai/explain` |
| Prometheus metrics | `http://localhost:8000/metrics` |

---

## Quick Reference: .env Variables cần kiểm tra trước demo

```ini
API_KEY=<your-demo-key>
ENVIRONMENT=development
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ids_db
POSTGRES_USER=ids_user
POSTGRES_PASSWORD=ids_password
MONGO_URI=mongodb://ids_mongo_user:ids_mongo_pass@localhost:27017/ids_logs?authSource=admin
REDIS_URL=redis://:ids_redis_pass@localhost:6379/0
ENABLE_EMAIL_ALERTS=false          # set true nếu SMTP đã cấu hình
CORS_ORIGINS=http://localhost:3000
```

---

## Troubleshooting

| Vấn đề | Nguyên nhân | Giải pháp |
|---|---|---|
| `401` trên tất cả requests | `API_KEY` trong `.env` không khớp với header | Kiểm tra `.env` và dùng đúng key trong `X-API-Key` |
| `400 Interface not found` | Tên interface sai | Chạy `python backend/scripts/list_interfaces.py` |
| `PermissionError: Npcap required` | Npcap chưa cài hoặc không ở WinPcap mode | Cài lại Npcap từ https://npcap.com/ với WinPcap API compatibility |
| Không có alerts | Traffic dưới `min_packets` hoặc tất cả Normal | Chạy `demo_attack_simulation.ps1`; giảm `min_packets` xuống 5 |
| WebSocket không nhận gì | Alert bị suppress (low confidence hoặc cooldown) | Kiểm tra `/api/sniffer/status` → `inference_runs`; giảm `ALERT_COOLDOWN_SECONDS` |
| `500` trên `/api/xai/explain` | Model chưa load hoặc `features.json` thiếu | Chạy `python backend/ml/create_dummy_models.py` rồi restart server |
| `model_loaded: false` trong health | Model files không tồn tại | Chạy `python backend/ml/create_dummy_models.py` |
| PostgreSQL connection refused | Container chưa chạy hoặc chưa healthy | `docker compose up -d postgres` và chờ `healthy` |
| `pytest` import errors | Thiếu dependencies | `pip install -r requirements.txt` |

---

## Demo Workflow cho Thesis Defense

### Terminal 1 — Backend
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Terminal 2 — Frontend
```bash
cd frontend && npm run dev
```

### Terminal 3 — WebSocket listener
```bash
wscat -c ws://localhost:8000/ws
```

### Terminal 4 — API commands
```bash
# Start pipeline
curl -X POST "http://localhost:8000/api/sniffer/start?interface=<INTERFACE>&model_name=ensemble" \
     -H "X-API-Key: <API_KEY>"

# Monitor
curl http://localhost:8000/api/sniffer/status -H "X-API-Key: <API_KEY>"
```

### Terminal 5 — Attack simulation
```bash
nmap -sS -p 1-1000 127.0.0.1
```

**Quan sát:**
- Alerts xuất hiện real-time trong Terminal 3 (WebSocket)
- Dashboard tại `http://localhost:3000` cập nhật tự động

### Screenshots cần chụp cho luận văn

1. `/health/detailed` — tất cả services connected
2. Swagger UI — tất cả endpoint groups
3. `401` response khi thiếu API key
4. `200` response khi có API key đúng
5. `422` response khi interface name có injection chars
6. Sniffer start success response
7. `/api/sniffer/status` với `processed_packets` > 0
8. WebSocket terminal nhận alert JSON
9. `/api/alerts/` response với alerts
10. PostgreSQL query kết quả
11. XAI explain response với `top_features`
12. Test suite output: tất cả tests pass
13. Frontend Overview dashboard
14. Frontend Alerts page với bảng alerts
15. Frontend AI Insights page (confusion matrix, metrics)
16. Frontend Network page
