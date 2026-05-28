# Security Model

Security controls implemented in the IDS backend codebase, the **actual threat surface** exposed by default configuration, and documented gaps. This reflects `backend/config.py`, `backend/api/`, and `backend/main.py` only.

---

## 1. Security goals (as implemented)

| Goal | Mechanism |
|------|-----------|
| Protect sniffer control | `X-API-Key` on `/api/sniffer/*` |
| Limit abuse on sensitive write paths | In-memory rate limits |
| Reduce injection via interface names | Regex validation before OS calls |
| Block unsafe production boot | `ENVIRONMENT=production` validator |
| Restrict browser origins | CORS allowlist |
| Cap upload size | `max_request_size` (default 10 MiB) |

**Not implemented:** JWT/session auth for APIs, RBAC, TLS termination in app, request signing, mTLS to databases.

---

## 2. API key authentication flow

**File:** `backend/api/dependencies.py`

```
Client Request
    │
    ├─ Header X-API-Key present?
    │     No  → 401 Invalid or missing API key
    │
    ├─ secrets.compare_digest(provided, settings.api_key)
    │     Fail → 401
    │
    └─ Pass → route handler runs
```

**Configuration:**

| Env var | Default (dev) | Production rule |
|---------|---------------|-----------------|
| `API_KEY` | `changeme-set-API_KEY-in-env` | ≥ 16 chars, not default |

**Scope:** Only `sniffer_router` applies router-level dependency:

```python
# backend/api/routes/sniffer.py
sniffer_router = APIRouter(dependencies=[Depends(verify_api_key)])
```

**All other REST routes and WebSocket are unauthenticated** unless an external reverse proxy adds auth.

---

## 3. Production configuration gate

**File:** `backend/config.py` — `Settings.validate_production_secrets`

When `ENVIRONMENT=production`, startup raises `RuntimeError` if:

- `SECRET_KEY` is default or length < 32
- `API_KEY` is default or length < 16
- `CORS_ORIGINS` empty

Development logs warnings but allows defaults.

**Verification script:** `scripts/verify_config_security.py`

---

## 4. CORS

**File:** `backend/main.py`

```python
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_credentials=True, ...)
```

| Environment | Origins |
|-------------|---------|
| `development` | `http://localhost:3000`, `http://127.0.0.1:3000` if `CORS_ORIGINS` unset |
| `production` | **Must** set `CORS_ORIGINS` comma-separated; empty list aborts startup |

Wildcard `*` is not used in code paths.

---

## 5. Rate limiting

**File:** `backend/api/middleware/rate_limit.py`

- **Algorithm:** Sliding window per `(client_ip, route_prefix)` in process memory
- **Storage:** `_windows` dict — **not shared across workers**
- **IP extraction:** `X-Forwarded-For` first hop, else `request.client.host`

| Prefix | Max requests / 60s |
|--------|-------------------|
| `/api/sniffer/` | 10 |
| `/api/whitelist/` | 30 |
| `/api/xai/` | 60 |

**Response:** HTTP 429 + `Retry-After` header

**Gaps:**

- No rate limit on `/api/alerts`, `/api/predictions`, `/api/traffic`, `/health`
- Reset on process restart
- Spoofable `X-Forwarded-For` without trusted proxy config

---

## 6. Input validation

**File:** `backend/api/validation.py`

| Validator | Used for |
|-----------|----------|
| `validate_ipv4` / `require_valid_ipv4` | Whitelist Pydantic models |
| `validate_port` | Whitelist port 1–65535 |
| `validate_protocol` | tcp, udp, icmp |
| `validate_interface` / `require_valid_interface` | Sniffer interface — blocks `;|&$` etc., max 64 chars |

**Additional sniffer checks** (`sniffer.py`):

- `min_packets` range 1–10000
- `prediction_mode` ∈ {once, window}
- Hardware `validate_interface()` from Scapy

**XAI** (`xai.py`): exact 20-feature key set vs `models/features.json`; NaN/inf sanitized in Pydantic validator.

---

## 7. Request size limit

```python
app = FastAPI(..., max_request_size=settings.max_request_size)
```

Default: `MAX_REQUEST_SIZE=10485760` (10 MB) from `.env.example`.

---

## 8. JWT and user accounts

**Config fields:** `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`

**Database:** `users` table with `password_hash` (bcrypt seed in `init_db.py`)

**Code search result:** No `python-jose`, OAuth2, or login routes in `backend/api/`. JWT settings are **unused** by HTTP layer today.

---

## 9. Email alert security

**File:** `backend/notifications/email.py`

- Gated by `ENABLE_EMAIL_ALERTS`
- Only `high` / `critical` severity
- Confidence ≥ 0.85
- Per-IP email cooldown (`EMAIL_COOLDOWN_SECONDS`)
- SMTP credentials from env (must not be committed)

---

## 10. Docker / runtime privileges

**File:** `docker-compose.yml` — `ids-backend` service:

```yaml
cap_add: [NET_RAW, NET_ADMIN]
privileged: true
```

Required for packet capture in containers but **increases container escape impact** — isolate on dedicated capture hosts.

**Other services:** `dashboard` (React frontend on port 3000), `postgres`, `mongodb`, `redis`, `nginx` (optional).

---

## 11. Threat surface matrix

| Asset | Exposure | Auth | Risk |
|-------|----------|------|------|
| Start/stop sniffing | `/api/sniffer/*` | API key | Medium if key leaked → full capture |
| Read all alerts | `/api/alerts/*` | None | High on untrusted networks |
| Batch predict | `/api/predictions/*` | None | Abuse / DoS |
| Whitelist modify | `/api/whitelist/*` | None + rate limit | Attacker could whitelist self |
| Live alerts | `/ws` | None | Information disclosure |
| Traffic stats | `/api/traffic/*` | None | Reconnaissance |
| SHAP explain | `/api/xai/*` | None + rate limit | CPU exhaustion (SHAP cost) |
| Health/metrics | `/health`, `/metrics` | None | Infra fingerprinting |
| PostgreSQL | Port 5432 in compose | DB password | Credential in compose file |
| Redis | Port 6379 | Password in compose | Same |
| MongoDB | Port 27017 | User/pass in compose | Same |

---

## 12. Security gaps (honest assessment)

1. **No API auth on most routes** — design assumes trusted network or external gateway.
2. **WebSocket open** — any client can subscribe to live attack feed.
3. **Legacy prediction endpoint** — unauthenticated model inference if `ml_model` loaded.
4. **In-memory rate limits** — ineffective with multiple replicas; spoofable forwarded IP.
5. **Default API_KEY in dev** — must rotate for any shared environment.
6. **Admin seed password** in `init_db.py` (`admin123`) — dangerous if init script run in production unchanged.
7. **No TLS in application** — terminate at nginx/load balancer (root-level `nginx/` reverse proxy config **not in repo**; `frontend/nginx.conf` is for SPA serving only).
8. **Prometheus /metrics** unauthenticated — may leak operational data.
9. **Email dispatch from sniffer thread** — may fail silently; not a direct vuln but ops blind spot.
10. **`backend/ml/inference.py`** — stale module; do not expose as CLI in production.
11. **CI runs Bandit** (`.github/workflows/ci.yml`) but does not gate merge by default (`|| true`).

---

## 13. Hardening recommendations (operational)

These are **not** implemented in code but align with current architecture:

| Control | Recommendation |
|---------|----------------|
| Edge auth | Put OAuth2/API gateway in front of all `/api/*` and `/ws` |
| Network | Bind Uvicorn to internal interface; no public Postgres/Redis/Mongo |
| Secrets | Use Docker secrets / vault; rotate `API_KEY` and DB passwords |
| Capture host | Dedicated VM with `privileged` only where needed |
| TLS | Add `nginx/` config with TLS termination (currently missing) |
| Metrics | Protect `/metrics` with network policy or basic auth at proxy |
| Production | Run `ENVIRONMENT=production` + `scripts/verify_config_security.py` |

---

## 14. Verification

```bash
# Should fail without key
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/sniffer/start
# Expect 401

# Should pass with key
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/sniffer/start \
  -H "X-API-Key: $API_KEY"

# Automated tests
pytest backend/tests/test_api_security.py -v
pytest backend/tests/test_rate_limiting.py -v
pytest backend/tests/test_input_validation.py -v

# Production config check
ENVIRONMENT=production python backend/scripts/verify_config_security.py
```

---

## 15. Related documents

- `docs/API_REFERENCE.md` — per-route auth table
- `docs/DEPLOYMENT_GUIDE.md` — env and Docker secrets
- `docs/TROUBLESHOOTING.md` — misconfiguration symptoms
