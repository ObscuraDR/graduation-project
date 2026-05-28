# Database and Persistence Schema

Persistence spans **PostgreSQL** (primary OLTP), **MongoDB** (flow log documents), and **Redis** (ephemeral cooldown/cache). Schema is managed via **Alembic migrations** (`backend/alembic/versions/`). Initial schema created by `001_initial_schema.py`.

**Modules:**

- `backend/database/models.py` — ORM
- `backend/database/connection.py` — clients
- `backend/database/repository.py` — CRUD helpers
- `backend/database/mongo_logger.py` — Mongo inserts
- `backend/cache/redis_cache.py` — Redis keys

---

## 1. PostgreSQL connection

**File:** `backend/database/connection.py`

```
postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}
```

Pool: `QueuePool`, `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`.

**Session factory:** `SessionLocal`  
**FastAPI dependency:** `get_db()` generator for request-scoped sessions.

**Init:**

```python
def init_db():
    Base.metadata.create_all(bind=engine)
```

Called from `main.py` lifespan and `backend/database/init_db.py` CLI.

---

## 2. PostgreSQL tables

**Base:** `declarative_base()` in `models.py`

### 2.1 `users`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| username | String(50) unique | |
| email | String(100) unique | |
| password_hash | String(255) | bcrypt via passlib in seed |
| role | String(20) | default `user` |
| created_at, updated_at | DateTime | |

**Usage:** Seeded by `init_db.py` (admin user). **No login API** in codebase.

---

### 2.2 `traffic_flows`

Stores flow snapshot when an **attack** is detected in the pipeline.

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Returned as `flow_id` to alerts |
| flow_key | String(200) unique indexed | 5-tuple key |
| src_ip, dst_ip | String(45) indexed | |
| src_port, dst_port | Integer nullable | |
| protocol | String(10) | |
| packet_count, byte_count | Integer | |
| forward_packets, backward_packets | Integer | |
| forward_bytes, backward_bytes | Integer | |
| syn_count … ack_count | Integer | TCP flag totals |
| flow_duration | Float | |
| start_time, last_seen | DateTime | |
| inter_arrival_time_mean | Float | |
| unique_dst_ports | Integer | |
| created_at | DateTime indexed | |

**Writer:** `TrafficFlowRepository.create_flow` — `pipeline/coordinator._save_flow_to_db`

---

### 2.3 `flow_features`

ML feature row linked to `traffic_flows.id`.

| Column | Type |
|--------|------|
| id | Integer PK |
| flow_id | FK → traffic_flows.id |
| flow_duration … packet_length_mean | Float/Integer (20 named columns) |
| feature_vector | JSON (full dict copy) |
| created_at | DateTime |

**Writer:** `FlowFeatureRepository.create_feature`

---

### 2.4 `attack_alerts`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| alert_id | String(50) unique indexed | UUID string from AlertManager |
| flow_id | FK nullable | Links to traffic_flows |
| source_ip, dest_ip | String(45) | Maps from alert `src_ip`/`dst_ip` |
| source_port, dest_port | Integer | |
| protocol | String(10) | |
| attack_type | String(50) indexed | |
| severity | String(20) | critical, high, medium, low |
| confidence | DECIMAL(5,2) | |
| correlated | Boolean | |
| original_severity | String(20) | |
| status | String(20) | active, resolved, ignored |
| is_resolved | Boolean | |
| resolved_at | DateTime | |
| notes | Text | |
| model_name, model_version | String | |
| all_probabilities | JSON | |
| timestamp | DateTime indexed | |

**Writers:**

- `AttackAlertRepository.create_alert` — pipeline alerts
- `legacy_routes` — read/update/delete via REST

---

### 2.5 `attack_history`

Per source IP attack rollups.

| Column | Type |
|--------|------|
| id | Integer PK |
| source_ip | String(45) indexed |
| attack_type | String(50) indexed |
| first_seen, last_seen | DateTime |
| attack_count | Integer |
| critical_count, high_count, medium_count, low_count | Integer |
| correlation_window_start | DateTime nullable |
| updated_at | DateTime |

**Writer:** `AttackHistoryRepository.update_or_create_history`

---

### 2.6 `models`

Registry of trained model metadata (not the pickle files themselves).

| Column | Type |
|--------|------|
| id | Integer PK |
| model_name, version | String |
| algorithm | String | RandomForest, XGBoost, … |
| accuracy, precision, recall, f1_score | DECIMAL nullable |
| file_path | String(255) |
| is_active | Boolean |
| created_at | DateTime |

**Usage:** `GET /api/models/`, `POST /api/models/load/{id}`

---

### 2.7 `whitelist`

| Column | Type |
|--------|------|
| id | Integer PK |
| ip_address | String(45) indexed |
| port | Integer nullable |
| protocol | String(10) nullable |
| reason | Text |
| added_by | Integer nullable |
| created_at | DateTime |

**Sync:** `POST /api/whitelist/add` also calls `alert_manager.add_to_whitelist(ip)`.

---

### 2.8 `metrics`

| Column | Type |
|--------|------|
| id | Integer PK |
| metric_name | String(100) |
| value | Float |
| timestamp | DateTime indexed |
| model_id | Integer nullable |
| metric_type | String(50) nullable |

Defined in ORM; **no active writer** found in hot-path modules.

---

## 3. Entity relationships (ASCII)

```
traffic_flows (1) ──────< (N) flow_features
      │
      │ (optional FK)
      ▼
attack_alerts

attack_history  (standalone, keyed by source_ip + attack_type)

whitelist, models, users, metrics  (standalone)
```

---

## 4. MongoDB

**Connection:** `get_mongo_client()` / `get_mongo_db()` in `connection.py`

| Setting | Env vars |
|---------|----------|
| URI | `MONGO_URI` (priority) or `mongodb://{MONGODB_HOST}:{MONGODB_PORT}/` |
| Database name | `MONGO_DB` or `MONGODB_DB` (default `ids_logs`) |

### Collection: `flow_logs`

**Module:** `backend/database/mongo_logger.py`  
**Function:** `log_flow_summary(flow_id, flow_stats, features)`

**Document shape:**

```json
{
  "flow_id": 42,
  "src_ip": "10.0.0.5",
  "dst_ip": "192.168.1.1",
  "src_port": 54321,
  "dst_port": 443,
  "protocol": "tcp",
  "timestamp": "2026-05-21T12:00:00",
  "features": { "flow_duration": 1.2, "packet_rate": 50.0, ... }
}
```

**When written:** Only on attack path in `PipelineCoordinator.packet_callback` (after PG flow save).

**Failure behavior:** Exception caught; warning logged; pipeline continues.

---

## 5. Redis

**Clients:**

- `get_redis_client()` in `connection.py` (used by health check)
- `RedisCache` in `cache/redis_cache.py` (used by AlertManager)

**Connection:**

- `REDIS_URL` if set, else `REDIS_HOST`/`REDIS_PORT`/`REDIS_DB`

### Key patterns

| Key | TTL | Purpose |
|-----|-----|---------|
| `alert_cooldown:{ip_address}` | `alert_cooldown` seconds (default 30) | Suppress repeat alerts per attacker IP |
| `whitelist:{ip}` | 300s default (helper) | Cache key generator — limited use |
| `model_metadata:{name}` | 300s | Cache key generator |
| `alert_stats:hourly` | — | Cache key generator |
| `system_stats:hourly` | — | Cache key generator |

**Alert cooldown API:**

```python
cache.set_alert_cooldown(ip, ttl_seconds)
cache.is_alert_in_cooldown(ip)
```

**Fallback:** If Redis unavailable, `AlertManager` uses in-memory `alert_history` dict.

**Admin:** `cache.delete_pattern("alert_cooldown:*")`, `flushdb` via `clear_all()`.

---

## 6. Persistence flow (attack detected)

```
Predictor.is_attack == True
    │
    ├─► PostgreSQL: TrafficFlow + FlowFeature  (coordinator._save_flow_to_db)
    │
    ├─► MongoDB: flow_logs.insert_one            (log_flow_summary)
    │
    └─► AlertManager.generate_alert
            ├─► PostgreSQL: attack_alerts + attack_history
            ├─► Redis: SETEX alert_cooldown:{ip}
            └─► WebSocket queue (not DB)
```

Normal traffic and sub-threshold predictions: **no** PG flow/Mongo write.

---

## 7. Database initialization and seed

**CLI:** `python backend/database/init_db.py`

1. `init_db()` — create tables (also handled by Alembic: `alembic upgrade head`)
2. `seed_data()`:
   - Admin user `admin` / `admin123` (if missing)
   - Whitelist `127.0.0.1`, `::1`

**Alembic migrations:** `backend/alembic/versions/001_initial_schema.py` — initial schema. Use `alembic revision --autogenerate -m "description"` for future changes.

**Known issue:** Line 52 references `Whititelist` (typo) — seed may **fail** at runtime until fixed in code.

---

## 8. Repository layer

**File:** `backend/database/repository.py`

| Class | Key methods |
|-------|-------------|
| `TrafficFlowRepository` | `create_flow`, `get_flow_by_key`, `update_flow` |
| `FlowFeatureRepository` | `create_feature` |
| `AttackAlertRepository` | `create_alert`, `get_alerts`, `update_alert_status` |
| `AttackHistoryRepository` | `update_or_create_history` |

AlertManager and coordinator use **new SessionLocal() per operation** with try/finally close — not request-scoped `get_db()`.

---

## 9. Verification

```bash
# Postgres tables
python backend/database/init_db.py

# Connectivity scripts
python backend/scripts/test_mongo_connection.py
python backend/scripts/test_redis_connection.py

# Integration tests
pytest backend/tests/test_db_integration.py -m integration -v

# Docker compose Postgres
docker compose exec postgres psql -U ids_user -d ids_db -c '\dt'
```

```javascript
// Mongo shell
use ids_logs
db.flow_logs.find().limit(3)

// Redis
KEYS alert_cooldown:*
```

---

## 10. Limitations

1. `traffic_flows.flow_key` unique constraint may reject duplicate keys on repeated attacks.
2. No FK from `attack_alerts` enforced at application level beyond ORM definition.
3. Mongo and PG writes are **not** in a single transaction.
4. Multi-worker deployments share DB but not in-memory flow state.
