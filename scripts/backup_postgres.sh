#!/bin/sh
# Automated Postgres backup — runs inside postgres container via cron
# Outputs: /backups/ragdb_YYYY-MM-DD_HH-MM.sql.gz
# Keeps last 7 days of backups

BACKUP_DIR=/backups
TIMESTAMP=$(date +%Y-%m-%d_%H-%M)
FILENAME="${BACKUP_DIR}/ragdb_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[backup] Starting Postgres dump at $TIMESTAMP..."
pg_dump -U rag ragdb | gzip > "$FILENAME"

if [ $? -eq 0 ]; then
    SIZE=$(du -sh "$FILENAME" | cut -f1)
    echo "[backup] Done — $FILENAME ($SIZE)"
else
    echo "[backup] ERROR — dump failed!"
    exit 1
fi

# Keep only last 7 days
find "$BACKUP_DIR" -name "ragdb_*.sql.gz" -mtime +7 -delete
echo "[backup] Cleanup done. Current backups:"
ls -lh "$BACKUP_DIR"
