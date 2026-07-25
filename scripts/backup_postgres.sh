#!/usr/bin/env bash
set -euo pipefail

: "${POSTGRES_BACKUP_URL:?Set POSTGRES_BACKUP_URL for pg_dump}"

backup_dir="${FOODAI_BACKUP_DIR:-./backups/postgres}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_path="${backup_dir}/foodai-${timestamp}.dump"

umask 077
mkdir -p "${backup_dir}"
pg_dump \
  --dbname="${POSTGRES_BACKUP_URL}" \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="${backup_path}"

printf '%s\n' "${backup_path}"
