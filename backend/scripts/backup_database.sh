#!/bin/bash
# Database Backup Script for IDS Backend
# Backs up the PostgreSQL database only

set -e

# Configuration
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
POSTGRES_BACKUP_FILE="${BACKUP_DIR}/postgres_backup_${TIMESTAMP}.sql.gz"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

echo "Starting database backup at ${TIMESTAMP}"

# PostgreSQL Backup
echo "Backing up PostgreSQL..."
if [ -n "${POSTGRES_HOST}" ]; then
    PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        -d "${POSTGRES_DB}" \
        --no-owner \
        --no-acl | gzip > "${POSTGRES_BACKUP_FILE}"
    echo "PostgreSQL backup completed: ${POSTGRES_BACKUP_FILE}"
else
    echo "Skipping PostgreSQL backup (POSTGRES_HOST not set)"
fi

# Cleanup old backups (keep last 7 days)
echo "Cleaning up old backups (older than 7 days)..."
find "${BACKUP_DIR}" -name "postgres_backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed successfully"
echo "PostgreSQL: ${POSTGRES_BACKUP_FILE}"
