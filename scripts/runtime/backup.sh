#!/usr/bin/env bash
# Automated daily backup for DriveMPVD.
#
# Creates a timestamped backup containing:
#   - PostgreSQL dump (custom format, restorable with pg_restore)
#   - Storage filesystem tar archive
#   - SHA256 checksums
#
# Retains backups for RETENTION_DAYS (default 7). Old backups are pruned
# automatically after a successful new backup is created.
#
# The script stops write-serving containers only for the duration of the
# pg_dump + tar (~seconds), then restarts them immediately. Downtime is
# minimal (typically < 30 seconds).
#
# Usage:
#   sudo bash scripts/runtime/backup.sh [options]
#
# Options:
#   --env-file PATH       Compose environment file (default: docker/.env)
#   --backup-dir PATH     Backup destination (default: /var/backups/drivempvd)
#   --retention-days N    Days to keep backups (default: 7)
#   --skip-restore-check  Skip full restore drill (faster daily backups)
#   -h, --help            Show this help
#
# Cron example (daily at 03:00 UTC):
#   0 3 * * * root bash /srv/drivempvd/scripts/runtime/backup.sh \
#     --env-file /srv/drivempvd/docker/.env 2>&1 | logger -t drivempvd-backup

set -Eeuo pipefail
umask 077

[[ $EUID -eq 0 ]] || {
  printf 'Run this backup script as root.\n' >&2
  exit 1
}

# ─── Parse arguments ────────────────────────────────────────────────────────

repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
environment_file="${repository_root}/docker/.env"
backup_dir="/var/backups/drivempvd"
retention_days=7
skip_restore_check=false

usage() {
  sed -n '2,/^set -/p' "${BASH_SOURCE[0]}" | grep '^#' | sed 's/^# \?//'
}

while (($#)); do
  case "$1" in
    --env-file)
      environment_file="${2:?--env-file requires a value}"
      shift 2
      ;;
    --backup-dir)
      backup_dir="${2:?--backup-dir requires a value}"
      shift 2
      ;;
    --retention-days)
      retention_days="${2:?--retention-days requires a value}"
      shift 2
      ;;
    --skip-restore-check)
      skip_restore_check=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

# ─── Mutex lock ─────────────────────────────────────────────────────────────

lock_file=/var/lock/drivempvd-backup.lock
exec 9>"$lock_file"
flock -n 9 || {
  printf 'Another DriveMPVD backup is already running.\n' >&2
  exit 1
}

# ─── Helpers ────────────────────────────────────────────────────────────────

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

compose_env_value() {
  python3 - "$environment_file" "$1" <<'PY'
from pathlib import Path
import sys
values = {}
for raw_line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    key, separator, value = line.partition("=")
    if not separator:
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    values[key] = value
print(values.get(sys.argv[2], ""))
PY
}

# ─── Validate environment ───────────────────────────────────────────────────

[[ -r "$environment_file" ]] || {
  printf 'Environment file not readable: %s\n' "$environment_file" >&2
  exit 1
}

compose=(docker compose --env-file "$environment_file" -f "${repository_root}/compose.yaml")
"${compose[@]}" config --quiet

storage_path=$(compose_env_value DRIVEMPVD_STORAGE_PATH)
[[ "$storage_path" == /* ]] || {
  printf 'DRIVEMPVD_STORAGE_PATH must be an absolute path.\n' >&2
  exit 1
}
storage_path=$(realpath -e -- "$storage_path")
[[ -d "$storage_path" ]] || {
  printf 'Storage path is not a directory: %s\n' "$storage_path" >&2
  exit 1
}

postgres_id=$("${compose[@]}" ps -q postgres 2>/dev/null || true)
[[ -n "$postgres_id" ]] || {
  printf 'PostgreSQL container is not running.\n' >&2
  exit 1
}

# ─── Create backup ──────────────────────────────────────────────────────────

backup_id="$(date -u +%Y%m%dT%H%M%SZ)"
backup_path="${backup_dir}/${backup_id}"
write_services=(nginx api worker)
services_stopped=false

cleanup() {
  if [[ "$services_stopped" == "true" ]]; then
    log "Restarting write-serving services..."
    "${compose[@]}" up -d --wait "${write_services[@]}" >/dev/null 2>&1 || true
    log "Write-serving services are up."
  fi
}
trap cleanup EXIT INT TERM

install -d -m 0700 "$backup_path"

log "Stopping write-serving services for coordinated snapshot..."
"${compose[@]}" stop "${write_services[@]}" >/dev/null
services_stopped=true

log "Dumping PostgreSQL database..."
docker exec "$postgres_id" sh -c \
  'pg_dump --format=custom --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  >"${backup_path}/database.dump"

log "Archiving storage filesystem..."
tar --numeric-owner -cpf "${backup_path}/storage.tar" \
  -C "$storage_path" .

log "Computing checksums..."
sha256sum "${backup_path}/database.dump" "${backup_path}/storage.tar" \
  >"${backup_path}/SHA256SUMS"

chmod 0600 "${backup_path}/database.dump" "${backup_path}/storage.tar" \
  "${backup_path}/SHA256SUMS"

log "Restarting write-serving services..."
"${compose[@]}" up -d --wait "${write_services[@]}" >/dev/null
services_stopped=false
log "Write-serving services are healthy."

# ─── Verify checksums ───────────────────────────────────────────────────────

log "Verifying backup checksums..."
(cd "$backup_path" && sha256sum --check SHA256SUMS)
log "Checksums verified."

# ─── Write metadata ─────────────────────────────────────────────────────────

db_size=$(wc -c < "${backup_path}/database.dump")
storage_size=$(wc -c < "${backup_path}/storage.tar")
migration_head=$(docker exec "$postgres_id" sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT version_num FROM alembic_version"' \
  2>/dev/null || echo "unknown")

cat >"${backup_path}/metadata.json" <<JSON
{
  "backup_id": "${backup_id}",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "migration_head": "${migration_head}",
  "database_bytes": ${db_size},
  "storage_bytes": ${storage_size},
  "retention_days": ${retention_days},
  "skip_restore_check": ${skip_restore_check}
}
JSON
chmod 0600 "${backup_path}/metadata.json"

log "Backup created: ${backup_path}"
log "  Database: $(numfmt --to=iec "$db_size")"
log "  Storage:  $(numfmt --to=iec "$storage_size")"
log "  Migration: ${migration_head}"

# ─── Retention: prune backups older than retention_days ─────────────────────

log "Pruning backups older than ${retention_days} days..."
pruned=0
while IFS= read -r -d '' old_backup; do
  dir_name=$(basename "$old_backup")
  log "  Removing old backup: ${dir_name}"
  rm -rf -- "$old_backup"
  ((pruned++))
done < <(find "$backup_dir" -maxdepth 1 -mindepth 1 -type d \
  -mtime "+${retention_days}" -print0 2>/dev/null)

if (( pruned > 0 )); then
  log "Pruned ${pruned} old backup(s)."
else
  log "No old backups to prune."
fi

# ─── List current backups ───────────────────────────────────────────────────

log "Current backups in ${backup_dir}:"
find "$backup_dir" -maxdepth 1 -mindepth 1 -type d -printf '  %f\n' 2>/dev/null | sort

log "Backup completed successfully."
