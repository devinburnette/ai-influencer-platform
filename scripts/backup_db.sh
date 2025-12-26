#!/bin/bash
# Database backup script for AI Influencer Platform

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETAIN_DAYS="${RETAIN_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/ai_influencer_$TIMESTAMP.sql.gz"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

echo "🔄 Starting database backup..."

# Run pg_dump inside the postgres container and compress
docker-compose exec -T postgres pg_dump -U aip_user ai_influencer | gzip > "$BACKUP_FILE"

# Check if backup was successful
if [ -s "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Backup created: $BACKUP_FILE ($BACKUP_SIZE)"
else
    echo "❌ Backup failed - file is empty"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Clean up old backups (older than RETAIN_DAYS)
echo "🧹 Cleaning up backups older than $RETAIN_DAYS days..."
find "$BACKUP_DIR" -name "ai_influencer_*.sql.gz" -type f -mtime +$RETAIN_DAYS -delete

# Show remaining backups
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/ai_influencer_*.sql.gz 2>/dev/null | wc -l)
echo "📁 Total backups: $BACKUP_COUNT"

echo "✨ Backup complete!"

