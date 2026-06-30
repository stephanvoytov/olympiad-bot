#!/bin/sh
# PostgreSQL backup — запускается по cron из pg-backup контейнера
set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="olympiadb_${TIMESTAMP}.sql.gz"

export PGPASSWORD="${PG_PASSWORD:-olympiad_secret}"

pg_dump \
  -h "${PG_HOST:-postgres}" \
  -U "${PG_USER:-olympiad}" \
  -d "${PG_DB:-olympiadb}" \
  --no-owner \
  --no-acl \
  | gzip > "/backups/${FILENAME}"

# Удаляем бекапы старше 7 дней
find /backups -name "olympiadb_*.sql.gz" -mtime +7 -delete

echo "Backup saved: ${FILENAME}"
