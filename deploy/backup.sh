#!/bin/sh
# Daily Postgres backup with rotation. Wire via cron (see docs/deployment.md).
set -e
cd "$(dirname "$0")/.."

compose="docker compose -f docker-compose.prod.yml"
backup_dir="${BACKUP_DIR:-./backups}"
retention=7

mkdir -p "$backup_dir"

# Load POSTGRES_USER / POSTGRES_DB for pg_dump.
. ./.env.prod

timestamp=$(date +%Y%m%d-%H%M%S)
out="$backup_dir/kinomania-$timestamp.sql.gz"

echo "### Dumping database to $out ..."
$compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$out"

echo "### Rotating: keeping the $retention most recent backups ..."
ls -1t "$backup_dir"/kinomania-*.sql.gz | tail -n +$((retention + 1)) | xargs -r rm -f

echo "### Backup complete: $out"
