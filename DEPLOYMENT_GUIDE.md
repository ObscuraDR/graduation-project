# IDS Backend Deployment Guide

This guide provides comprehensive instructions for deploying the IDS Backend to production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Security Hardening](#security-hardening)
4. [Docker Deployment](#docker-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Monitoring & Logging](#monitoring--logging)
7. [Backup & Recovery](#backup--recovery)
8. [Performance Tuning](#performance-tuning)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Operating System**: Ubuntu 20.04+ or CentOS 7+
- **CPU**: 4+ cores recommended
- **RAM**: 8GB minimum, 16GB recommended
- **Disk**: 50GB minimum (SSD recommended)
- **Network**: Gigabit network interface for packet capture

### Software Requirements

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.10+ (for local development)
- PostgreSQL 15+
- MongoDB 7+
- Redis 7+
- Npcap (Windows) or libpcap (Linux) for packet capture

## Environment Configuration

### 1. Generate Secure Keys

```bash
# Generate API Key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate JWT Secret Key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and update the following critical values:

```bash
# Security
API_KEY=<generated-api-key>
SECRET_KEY=<generated-secret-key>

# Database Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=ids_db
POSTGRES_USER=ids_user
POSTGRES_PASSWORD=<strong-postgres-password>

# MongoDB Configuration
MONGODB_HOST=mongodb
MONGODB_PORT=27017
MONGODB_DB=ids_logs

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379

# CORS (comma-separated list of allowed origins)
CORS_ORIGINS=https://your-frontend-domain.com,https://admin.your-domain.com

# Request Size Limit (10MB default)
MAX_REQUEST_SIZE=10485760

# Email Alerts (optional)
ENABLE_EMAIL_ALERTS=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=<app-specific-password>
SMTP_FROM=IDS System <noreply@your-domain.com>
SMTP_TO=soc-team@your-domain.com
EMAIL_COOLDOWN_SECONDS=60
```

### 3. Configure CORS Origins

Update `CORS_ORIGINS` to include only your actual frontend domains:

```bash
# Production example
CORS_ORIGINS=https://ids.yourcompany.com,https://admin.yourcompany.com

# Development example
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

## Security Hardening

### 1. Network Security

- Use firewall rules to restrict access to database ports
- Only expose necessary ports (80/443 for web, 8000 for API behind reverse proxy)
- Use VPN or SSH bastion host for administrative access

### 2. SSL/TLS Configuration

Configure Nginx with SSL certificates:

```nginx
server {
    listen 443 ssl http2;
    server_name ids.yourcompany.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Rate Limiting

Rate limiting is already implemented in `backend/api/middleware/rate_limit.py`. Adjust limits in `backend/config.py` if needed.

### 4. API Key Protection

- Never commit `.env` file to version control
- Rotate API keys regularly (every 90 days)
- Use different API keys for different environments

## Docker Deployment

### 1. Build and Start Services

```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f backend
```

### 2. Initialize Database

```bash
# Database initialization happens automatically on startup
# Check logs for confirmation
docker-compose logs backend | grep "Database initialized"
```

### 3. Verify Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "IDS Backend",
  "version": "1.0.0",
  "pipeline_running": false
}
```

### 4. Start Packet Sniffer

```bash
# Start sniffer on specific interface
curl -X POST http://localhost:8000/api/sniffer/start \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "interface": "eth0",
    "dry_run": false
  }'
```

## Kubernetes Deployment

### 1. Create Kubernetes Secrets

```bash
kubectl create secret generic ids-secrets \
  --from-literal=api-key=your-api-key \
  --from-literal=secret-key=your-secret-key \
  --from-literal=postgres-password=your-postgres-password
```

### 2. Deploy PostgreSQL

```yaml
# postgres-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        env:
        - name: POSTGRES_DB
          value: "ids_db"
        - name: POSTGRES_USER
          value: "ids_user"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: ids-secrets
              key: postgres-password
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
```

### 3. Deploy Backend

```yaml
# backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ids-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ids-backend
  template:
    metadata:
      labels:
        app: ids-backend
    spec:
      containers:
      - name: backend
        image: ids-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: ids-secrets
              key: api-key
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: ids-secrets
              key: secret-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
```

### 4. Apply Deployments

```bash
kubectl apply -f postgres-deployment.yaml
kubectl apply -f backend-deployment.yaml
kubectl apply -f service.yaml
```

## Monitoring & Logging

### 1. Prometheus Metrics

The backend exposes metrics at `/metrics` endpoint. Configure Prometheus scrape config:

```yaml
scrape_configs:
  - job_name: 'ids-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
```

### 2. Structured Logging

Logs are now in JSON format with correlation IDs. View logs:

```bash
# Docker Compose
docker-compose logs -f backend | jq

# Kubernetes
kubectl logs -f deployment/ids-backend | jq
```

### 3. Log Rotation

Configure log rotation in `/etc/logrotate.d/ids-backend`:

```
/path/to/logs/backend.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 www-data www-data
}
```

## Backup & Recovery

### 1. Automated Backups

Run the backup script via cron:

```bash
# Add to crontab
0 2 * * * /path/to/scripts/backup_database.sh
```

### 2. Manual Backup

```bash
# PostgreSQL
pg_dump -h postgres -U ids_user -d ids_db > backup.sql

# MongoDB
mongodump --host mongodb --port 27017 --db ids_logs --archive=mongodb_backup.gz --gzip
```

### 3. Restore from Backup

```bash
# PostgreSQL
psql -h postgres -U ids_user -d ids_db < backup.sql

# MongoDB
mongorestore --host mongodb --port 27017 --db ids_logs --archive=mongodb_backup.gz --gzip
```

## Performance Tuning

### 1. Database Optimization

PostgreSQL configuration in `docker-compose.yml`:

```yaml
command:
  - "postgres"
  - "-c"
  - "shared_buffers=256MB"
  - "-c"
  - "max_connections=200"
  - "-c"
  - "work_mem=4MB"
```

### 2. Redis Configuration

```yaml
command:
  - "redis-server"
  - "--maxmemory"
  - "256mb"
  - "--maxmemory-policy"
  - "allkeys-lru"
```

### 3. Connection Pooling

Connection pooling is configured in `backend/database/connection.py`. Adjust pool size in `backend/config.py`:

```python
pool_size = 20
max_overflow = 10
pool_timeout = 30
```

### 4. Load Testing

Run load tests with Locust:

```bash
# Install locust
pip install locust

# Run load tests
cd loadtests
locust -f locustfile.py --host=http://localhost:8000

# Headless mode
locust -f locustfile.py --host=http://localhost:8000 --headless -u 100 -r 10 -t 1m
```

## Troubleshooting

### 1. Backend Won't Start

Check logs:
```bash
docker-compose logs backend
```

Common issues:
- Database connection failed: Check database credentials and network
- Port already in use: Change `API_PORT` in `.env`
- Missing dependencies: Rebuild with `docker-compose build --no-cache`

### 2. Packet Sniffer Fails

Check Npcap/libpcap installation:
```bash
# Linux
sudo tcpdump -D

# Windows
npcap -h
```

Check interface availability:
```bash
curl http://localhost:8000/api/sniffer/status
```

### 3. High Memory Usage

- Reduce `pool_size` in database connection
- Enable Redis caching to reduce database load
- Check for memory leaks in custom code

### 4. Slow Performance

- Check database query performance with `EXPLAIN ANALYZE`
- Enable Redis caching for frequently accessed data
- Review Prometheus metrics for bottlenecks
- Consider horizontal scaling with Kubernetes

### 5. Email Alerts Not Sending

Verify SMTP configuration:
```bash
# Test SMTP connection
telnet smtp.gmail.com 587
```

Check email service logs:
```bash
docker-compose logs backend | grep email
```

## Production Checklist

Before going to production, ensure:

- [ ] All secrets are generated and stored securely
- [ ] CORS origins are configured to specific domains
- [ ] SSL/TLS certificates are installed
- [ ] Firewall rules are configured
- [ ] Backup schedule is set up
- [ ] Monitoring (Prometheus) is configured
- [ ] Log rotation is enabled
- [ ] Load testing has been performed
- [ ] Rate limiting is tested
- [ ] API key rotation procedure is documented
- [ ] Disaster recovery plan is tested
- [ ] CI/CD pipeline is working
- [ ] Security scan (Bandit) passes

## Support

For issues or questions:
- Check logs in `logs/backend.log`
- Review API documentation in `API_DOCUMENTATION.md`
- Check troubleshooting section above
- Review COMMANDS.md for common operations
