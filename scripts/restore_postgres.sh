#!/usr/bin/env bash
set -euo pipefail

: "${POSTGRES_RESTORE_URL:?Set POSTGRES_RESTORE_URL for pg_restore}"
: "${FOODAI_RESTORE_FILE:?Set FOODAI_RESTORE_FILE to a .dump file}"

if [[ "${FOODAI_RESTORE_CONFIRM:-}" != "restore-foodai" ]]; then
  printf '%s\n' "Set FOODAI_RESTORE_CONFIRM=restore-foodai to confirm destructive restore." >&2
  exit 2
fi

if [[ ! -f "${FOODAI_RESTORE_FILE}" ]]; then
  printf '%s\n' "Backup file not found: ${FOODAI_RESTORE_FILE}" >&2
  exit 2
fi

pg_restore \
  --dbname="${POSTGRES_RESTORE_URL}" \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  "${FOODAI_RESTORE_FILE}"
