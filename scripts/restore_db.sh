#!/bin/bash
# Database restore script for AI Influencer Platform

set -e

BACKUP_DIR="${BACKUP_DIR:-./backups}"

# Check if backup file is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    ls -lh "$BACKUP_DIR"/ai_influencer_*.sql.gz 2>/dev/null || echo "  No backups found in $BACKUP_DIR"
    exit 1
fi

BACKUP_FILE="$1"

# Check if file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "⚠️  WARNING: This will replace ALL data in the database!"
echo "   Backup file: $BACKUP_FILE"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo "🔄 Restoring database from $BACKUP_FILE..."

# Drop existing connections and recreate database
docker-compose exec -T postgres psql -U aip_user -d postgres -c "
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE datname = 'ai_influencer' AND pid <> pg_backend_pid();
"

docker-compose exec -T postgres psql -U aip_user -d postgres -c "DROP DATABASE IF EXISTS ai_influencer;"
docker-compose exec -T postgres psql -U aip_user -d postgres -c "CREATE DATABASE ai_influencer OWNER aip_user;"

# Restore from backup
gunzip -c "$BACKUP_FILE" | docker-compose exec -T postgres psql -U aip_user -d ai_influencer

echo "✅ Database restored successfully!"
echo ""
echo "⚠️  You may need to restart the backend to reconnect:"
echo "   docker-compose restart backend celery-worker celery-beat"

