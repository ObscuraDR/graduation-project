# Database Backup Script for IDS Backend (PowerShell)
# Backs up PostgreSQL and MongoDB databases

$ErrorActionPreference = "Stop"

# Configuration
$BACKUP_DIR = ".\backups"
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$POSTGRES_BACKUP_FILE = "$BACKUP_DIR\postgres_backup_$TIMESTAMP.sql.gz"
$MONGODB_BACKUP_FILE = "$BACKUP_DIR\mongodb_backup_$TIMESTAMP.archive.gz"

# Create backup directory
New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null

Write-Host "Starting database backup at $TIMESTAMP"

# PostgreSQL Backup
Write-Host "Backing up PostgreSQL..."
if ($env:POSTGRES_HOST) {
    $env:PGPASSWORD = $env:POSTGRES_PASSWORD
    pg_dump `
        -h $env:POSTGRES_HOST `
        -p $env:POSTGRES_PORT `
        -U $env:POSTGRES_USER `
        -d $env:POSTGRES_DB `
        --no-owner `
        --no-acl | gzip > $POSTGRES_BACKUP_FILE
    Write-Host "PostgreSQL backup completed: $POSTGRES_BACKUP_FILE"
} else {
    Write-Host "Skipping PostgreSQL backup (POSTGRES_HOST not set)"
}

# MongoDB Backup
Write-Host "Backing up MongoDB..."
if ($env:MONGODB_HOST) {
    mongodump `
        --host=$env:MONGODB_HOST `
        --port=$env:MONGODB_PORT `
        --db=$env:MONGODB_DB `
        --archive=$MONGODB_BACKUP_FILE `
        --gzip
    Write-Host "MongoDB backup completed: $MONGODB_BACKUP_FILE"
} else {
    Write-Host "Skipping MongoDB backup (MONGODB_HOST not set)"
}

# Cleanup old backups (keep last 7 days)
Write-Host "Cleaning up old backups (older than 7 days)..."
Get-ChildItem -Path $BACKUP_DIR -Filter "postgres_backup_*.sql.gz" | 
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | 
    Remove-Item -Force

Get-ChildItem -Path $BACKUP_DIR -Filter "mongodb_backup_*.archive.gz" | 
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | 
    Remove-Item -Force

Write-Host "Backup completed successfully"
Write-Host "PostgreSQL: $POSTGRES_BACKUP_FILE"
Write-Host "MongoDB: $MONGODB_BACKUP_FILE"
