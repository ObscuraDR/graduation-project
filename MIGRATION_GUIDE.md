# Database Migration Guide: 3 → 1 (MongoDB & Redis → PostgreSQL)

## Tóm Tắt Thay Đổi

Dự án đã được cải thiện để **chỉ sử dụng PostgreSQL** thay vì 3 database:

| Trước | Sau |
|-------|-----|
| PostgreSQL + MongoDB + Redis | PostgreSQL (only) |
| 3 Docker services | 1 Docker service |
| Phức tạp, nhiều dependencies | Đơn giản, dễ maintain |

---

## Chi Tiết Thay Đổi

### 1. MongoDB → PostgreSQL
- **Flow Logs**: Chuyển từ `MongoDB.flow_logs` collection sang `PostgreSQL.flow_logs` table
- **Lợi ích**: Giảm 1 database, tất cả data trong 1 nơi
- **Dữ liệu**: Chỉ thêm JSON column `features` để lưu flow features

### 2. Redis → In-Memory Cache
- **Alert Cooldown**: Đã sử dụng in-memory dictionary (không cần Redis)
- **Whitelist/Blacklist**: Lưu trong PostgreSQL, load vào memory khi startup
- **Lợi ích**: 
  - Giảm latency (in-memory so với network Redis)
  - Giảm 1 service (Redis)
  - Tự động expire TTL

### 3. Cache Implementation
- **File**: `backend/cache/redis_cache.py` → `SimpleCache` class
- **TTL Support**: Yes (auto-expire)
- **Persistence**: PostgreSQL (if configured)

---

## Những File Đã Thay Đổi

1. **backend/database/models.py**
   - ✅ Thêm: `FlowLog` model mới

2. **backend/database/mongo_logger.py**
   - ✅ Rewrite: Sử dụng PostgreSQL thay vì MongoDB

3. **backend/cache/redis_cache.py**
   - ✅ Rewrite: Sử dụng in-memory dict thay vì Redis

4. **backend/database/connection.py**
   - ✅ Xóa: `get_mongo_client()`, `get_mongo_db()` functions
   - ✅ Giữ: PostgreSQL connection

5. **backend/config.py**
   - ✅ Xóa: MongoDB settings (`mongodb_host`, `mongodb_port`, `mongo_uri`, etc.)
   - ✅ Xóa: Redis settings (`redis_host`, `redis_port`, `redis_url`, etc.)

6. **backend/main.py**
   - ✅ Update: Health check endpoint (remove MongoDB & Redis checks)

7. **.env.example**
   - ✅ Xóa: MongoDB env variables
   - ✅ Xóa: Redis env variables

8. **requirements-optional.txt**
   - ✅ Xóa: `pymongo`, `redis` packages

9. **docker-compose.yml**
   - ✅ Giữ: PostgreSQL service
   - ✅ Xóa: MongoDB service
   - ✅ Xóa: Redis service

10. **README.md**
    - ✅ Update: Tech Stack table
    - ✅ Update: Project structure documentation

11. **backend/alembic/versions/001_initial_schema.py**
    - ✅ Thêm: `flow_logs` table creation in migration

---

## Hướng Dẫn Nâng Cấp

### Option 1: Fresh Installation (Khuyến Khích)
```bash
# Xóa old services
docker-compose down -v

# Cập nhật code
git pull origin main

# Tạo .env từ template mới
cp .env.example .env

# Start PostgreSQL
docker-compose up -d postgres

# Chạy migrations (sẽ tạo flow_logs table)
alembic upgrade head

# Start backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Start frontend
cd frontend && npm install && npm run dev
```

### Option 2: Upgrade Existing Installation
```bash
# 1. Stop running services
docker-compose down

# 2. Backup PostgreSQL (nếu có dữ liệu quan trọng)
docker run --rm -v ids-postgres:/data -v $(pwd):/backup \
  postgres:14-alpine \
  pg_dump -U ids_user -d ids_db > /backup/backup.sql

# 3. Update code
git pull origin main

# 4. Update .env (xóa MONGODB_*, REDIS_* variables)
nano .env

# 5. Start PostgreSQL
docker-compose up -d postgres

# 6. Run migrations (tạo flow_logs table)
alembic upgrade head

# 7. Start backend & frontend như bình thường
```

---

## Các Lợi Ích

✅ **Giảm độ phức tạp**
- Từ 3 database xuống 1
- Giảm Docker services
- Ít dependencies

✅ **Cải Thiện Hiệu Năng**
- In-memory cache nhanh hơn Redis (cùng process)
- Giảm network latency
- Giảm memory footprint

✅ **Dễ Bảo Trì**
- 1 database connection string
- Không cần setup MongoDB & Redis
- Migration về PostgreSQL (Alembic)

✅ **Tiết Kiệm Tài Nguyên**
- 1 container PostgreSQL thay vì 3 containers
- Giảm CPU/Memory usage

---

## Backward Compatibility

⚠️ **Breaking Changes:**
- MongoDB URI không được support nữa
- Redis cache không được support nữa
- Nếu bạn có data trong MongoDB, cần migrate thủ công

💡 **Để keep old data từ MongoDB:**
```bash
# Export từ MongoDB
mongoexport --collection flow_logs --out flow_logs.json --db ids_logs

# Sau đó import vào PostgreSQL
# (Script tùy chỉnh - liên hệ team dev nếu cần)
```

---

## Testing

```bash
# Check PostgreSQL connection
python -c "from backend.database.connection import engine; engine.execute('SELECT 1')"

# Check in-memory cache
python -c "from backend.cache.redis_cache import get_cache; print(get_cache().is_connected())"

# Run tests
pytest backend/tests/

# Check health endpoint
curl http://localhost:8000/health/detailed
```

---

## Support

Nếu gặp lỗi:
1. Kiểm tra `.env` - xác nhận không có `MONGO_*` hay `REDIS_*` variables
2. Chạy migrations: `alembic upgrade head`
3. Kiểm tra logs: `tail -f logs/backend.log`
4. Contact: GitHub Issues

---

**Ngày cập nhật**: 2026-06-11
**Version**: 2.0 (PostgreSQL-only)
