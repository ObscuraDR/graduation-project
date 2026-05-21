# FINAL DEMO CHECKLIST
## Machine Learning-Based IDS — Thesis Defense Demo

**Run this checklist top-to-bottom before and during the defense demo.**  
Replace `<INTERFACE>` with your actual interface name (run `python scripts/list_interfaces.py` to find it).  
Replace `<API_KEY>` with the value of `API_KEY` in your `.env` file.

---

| # | Task | Command | Expected Output | Status |
|---|---|---|---|---|
| **SETUP** | | | | |
| 1 | Start Docker PostgreSQL | `docker-compose up -d postgres` | Container starts; no error output | ☐ |
| 2 | Verify PostgreSQL healthy | `docker-compose ps postgres` | State shows `healthy` | ☐ |
| 3 | Initialize database tables | `python backend/database/init_db.py` | "All tables created successfully" (or "already exist") | ☐ |
| 4 | Verify models exist | `dir models\` | `ensemble.pkl`, `ensemble_scaler.pkl`, `ensemble_encoder.pkl`, `features.json` present | ☐ |
| 5 | Install wscat (if needed) | `npm install -g wscat` | `wscat` command available | ☐ |
| **SERVER** | | | | |
| 6 | Start Uvicorn backend | `uvicorn backend.main:app --host 0.0.0.0 --port 8000` | "Application startup complete" in logs | ☐ |
| 7 | Health check | `curl http://localhost:8000/health` | `{"status": "healthy", ...}` | ☐ |
| 8 | Open Swagger UI | Browser → `http://localhost:8000/docs` | All endpoint groups visible (sniffer, alerts, whitelist, xai, traffic) | ☐ |
| **SECURITY** | | | | |
| 9 | Test API key rejection | `curl http://localhost:8000/api/sniffer/status` | `HTTP 401` `{"detail": "Invalid or missing API key"}` | ☐ |
| 10 | Test API key acceptance | `curl http://localhost:8000/api/sniffer/status -H "X-API-Key: <API_KEY>"` | `HTTP 200` `{"is_running": false, ...}` | ☐ |
| 11 | Test rate limit (optional) | Send 11 rapid requests to `/api/sniffer/status` with valid key | 11th request returns `HTTP 429` with `retry_after_seconds` | ☐ |
| **WEBSOCKET** | | | | |
| 12 | Open WebSocket connection | `wscat -c ws://localhost:8000/ws` | "Connected (press CTRL+C to quit)" | ☐ |
| 13 | Keep WebSocket terminal visible | — | Terminal stays open; ready to receive alerts | ☐ |
| **SNIFFER PIPELINE** | | | | |
| 14 | List available interfaces | `python scripts/list_interfaces.py` | List of interface names; note the recommended one | ☐ |
| 15 | Start sniffer pipeline | `curl -X POST "http://localhost:8000/api/sniffer/start?interface=<INTERFACE>&model_name=ensemble&min_packets=10" -H "X-API-Key: <API_KEY>"` | `{"success": true, "status": "running", "interface": "<INTERFACE>"}` | ☐ |
| 16 | Verify pipeline running | `curl http://localhost:8000/api/sniffer/status -H "X-API-Key: <API_KEY>"` | `{"is_running": true, "processed_packets": N, ...}` where N > 0 | ☐ |
| **ATTACK SIMULATION** | | | | |
| 17 | Run attack simulation script | `.\scripts\demo_attack_simulation.ps1` | Script runs; shows attack commands executing | ☐ |
| 18 | (Optional) nmap port scan | `nmap -sS -p 1-1000 <target_ip>` | nmap output showing ports scanned | ☐ |
| 19 | Monitor packet count | `curl http://localhost:8000/api/sniffer/status -H "X-API-Key: <API_KEY>"` | `processed_packets` increasing; `inference_runs` > 0 | ☐ |
| 20 | Observe WebSocket alert | Watch wscat terminal | JSON alert appears: `{"attack_type": "PortScan", "severity": "high", "confidence": 0.XX, ...}` | ☐ |
| **ALERTS & DATABASE** | | | | |
| 21 | Check alerts via API | `curl http://localhost:8000/api/alerts/ -H "X-API-Key: <API_KEY>"` | JSON array with at least one alert containing `alert_id`, `attack_type`, `severity`, `confidence`, `src_ip` | ☐ |
| 22 | Check alerts in PostgreSQL | `docker exec -it <postgres_container> psql -U ids_user -d ids_db -c "SELECT id, attack_type, severity, confidence, source_ip, created_at FROM attack_alerts ORDER BY created_at DESC LIMIT 5;"` | Table rows showing recent alerts | ☐ |
| 23 | Check traffic flows in DB | `docker exec -it <postgres_container> psql -U ids_user -d ids_db -c "SELECT id, src_ip, dst_ip, protocol, packet_count FROM traffic_flows ORDER BY id DESC LIMIT 5;"` | Table rows showing captured flows | ☐ |
| **EMAIL ALERT** | | | | |
| 24 | Verify email config | Check `.env` for `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_RECIPIENT`, `ENABLE_EMAIL_ALERTS=true` | All values set | ☐ |
| 25 | Check email inbox | Open email client for `ALERT_EMAIL_RECIPIENT` | Email received with subject "IDS Alert: [attack_type]" for high/critical severity alert | ☐ |
| **EXPLAINABILITY** | | | | |
| 26 | Call XAI explain endpoint | `curl -X POST http://localhost:8000/api/xai/explain -H "Content-Type: application/json" -H "X-API-Key: <API_KEY>" -d "{\"model_name\": \"ensemble\", \"features\": {\"flow_duration\": 1.5, \"total_fwd_packets\": 500, \"total_bwd_packets\": 10, \"total_fwd_bytes\": 50000, \"total_bwd_bytes\": 1000, \"avg_packet_size\": 100.0, \"packet_rate\": 1200.0, \"byte_rate\": 98000.0, \"syn_count\": 450, \"fin_count\": 2, \"rst_count\": 5, \"psh_count\": 10, \"ack_count\": 50, \"unique_dst_ports\": 1, \"inter_arrival_time_mean\": 0.001, \"fwd_packet_rate\": 1100.0, \"bwd_packet_rate\": 100.0, \"fwd_byte_rate\": 90000.0, \"bwd_byte_rate\": 8000.0, \"packet_length_mean\": 100.0}}"` | `{"success": true, "data": {"predicted_label": "...", "confidence": 0.XX, "top_features": [...], "shap_values": {...}}}` | ☐ |
| 27 | Verify SHAP top features | Inspect response `data.top_features` | Array of 5 features each with `feature`, `value`, `shap_value` fields | ☐ |
| **CLEANUP** | | | | |
| 28 | Stop sniffer pipeline | `curl -X POST http://localhost:8000/api/sniffer/stop -H "X-API-Key: <API_KEY>"` | `{"success": true, "status": "stopped"}` | ☐ |
| 29 | Verify pipeline stopped | `curl http://localhost:8000/api/sniffer/status -H "X-API-Key: <API_KEY>"` | `{"is_running": false, ...}` | ☐ |
| **TEST SUITE** | | | | |
| 30 | Run full test suite | `pytest backend/tests/ -v` | `58 passed` — no failures, no errors | ☐ |
| 31 | Run with coverage (optional) | `pytest backend/tests/ --cov=backend --cov-report=term-missing` | Coverage report displayed; all critical modules covered | ☐ |

---

## Quick Reference: Key URLs

| Resource | URL |
|---|---|
| Health check | `http://localhost:8000/health` |
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |
| WebSocket | `ws://localhost:8000/ws` |
| Sniffer status | `http://localhost:8000/api/sniffer/status` |
| Alerts | `http://localhost:8000/api/alerts/` |
| XAI explain | `http://localhost:8000/api/xai/explain` |
| Traffic stats | `http://localhost:8000/api/traffic/stats` |

## Quick Reference: Environment Variables to Verify Before Demo

```
API_KEY=<your-demo-key>
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ids_db
POSTGRES_USER=ids_user
POSTGRES_PASSWORD=<password>
ENABLE_EMAIL_ALERTS=true          # set to false if SMTP not configured
SMTP_HOST=<smtp-server>
SMTP_USER=<email>
SMTP_PASSWORD=<password>
ALERT_EMAIL_RECIPIENT=<recipient>
ALERT_CONFIDENCE_THRESHOLD=0.75
ALERT_COOLDOWN_SECONDS=60
```

## Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| `401` on all requests | `API_KEY` in `.env` does not match header value | Check `.env` and use exact same key in `X-API-Key` header |
| Sniffer returns `400 Interface not found` | Wrong interface name | Run `python scripts/list_interfaces.py` and use exact name shown |
| `PermissionError: Npcap required` | Npcap not installed or not in WinPcap-compatible mode | Reinstall Npcap from https://npcap.com/ with WinPcap API compatibility checked |
| No alerts generated | Traffic below `min_packets` threshold or all Normal | Run `demo_attack_simulation.ps1`; lower `min_packets` to 5 |
| WebSocket shows nothing | Alert suppressed (low confidence or cooldown) | Check `/api/sniffer/status` for `inference_runs`; reduce `ALERT_COOLDOWN_SECONDS` |
| `500` on `/api/xai/explain` | Model not loaded or `features.json` missing | Run `python backend/ml/create_dummy_models.py` then restart server |
| PostgreSQL connection refused | Container not running or not healthy | `docker-compose up -d postgres` and wait for `healthy` state |
| `pytest` import errors | Missing dependencies | `pip install -r requirements.txt` |
