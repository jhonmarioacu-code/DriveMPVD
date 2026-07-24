#!/usr/bin/env bash
# Create a coordinated local backup and prove it restores in disposable storage.
set -Eeuo pipefail

umask 077

[[ $EUID -eq 0 ]] || {
  printf 'Run this backup and restore drill as root.\n' >&2
  exit 1
}

lock_file=/var/lock/drivempvd-backup-restore.lock
exec 9>"$lock_file"
flock -n 9 || {
  printf 'Another DriveMPVD backup or restore drill is already running.\n' >&2
  exit 1
}

repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
environment_file=${DRIVEMPVD_COMPOSE_ENV_FILE:-"$repository_root/docker/.env"}
case "$environment_file" in
  /*) ;;
  *) environment_file="$repository_root/$environment_file" ;;
esac
export DRIVEMPVD_COMPOSE_ENV_FILE="$environment_file"
cd "$repository_root"
backup_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
backup_root="/var/backups/drivempvd/$backup_id"
restore_root=$(mktemp -d /var/lib/drivempvd/restore-drill.XXXXXX)
restore_container="drivempvd-restore-drill-$$"
restore_password=$(openssl rand -hex 32)
services_stopped=false
compose=(docker compose --env-file "$environment_file" -f "$repository_root/compose.yaml")
write_services=(nginx api worker)

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

cleanup() {
  docker rm -f "$restore_container" >/dev/null 2>&1 || true
  case "$restore_root" in
    /var/lib/drivempvd/restore-drill.*) rm -rf -- "$restore_root" ;;
  esac
  if [[ "$services_stopped" == "true" ]]; then
    "${compose[@]}" up -d --wait "${write_services[@]}" >/dev/null
  fi
}
trap cleanup EXIT INT TERM

[[ -r "$environment_file" ]] || {
  printf 'Compose environment is not readable: %s\n' "$environment_file" >&2
  exit 1
}
"${compose[@]}" config --quiet
storage_path=$(compose_env_value DRIVEMPVD_STORAGE_PATH)
[[ "$storage_path" == /* ]] || {
  printf 'DRIVEMPVD_STORAGE_PATH must be an absolute path.\n' >&2
  exit 1
}
storage_path=$(realpath -e -- "$storage_path")
[[ "$storage_path" != "/" ]] || {
  printf 'DRIVEMPVD_STORAGE_PATH must not be the filesystem root.\n' >&2
  exit 1
}
[[ -d "$storage_path" ]] || {
  printf 'Storage path is not a directory: %s\n' "$storage_path" >&2
  exit 1
}
install -d -m 0700 "$backup_root"
postgres_id=$("${compose[@]}" ps -q postgres)
[[ -n "$postgres_id" ]] || {
  printf 'PostgreSQL is not running.\n' >&2
  exit 1
}
restore_image=${DRIVEMPVD_RESTORE_IMAGE:-}
if [[ -z "$restore_image" ]]; then
  restore_image=$(docker inspect --format '{{.Config.Image}}' "$postgres_id")
fi
[[ "$restore_image" == drivempvd-postgres:* ]] || {
  printf 'PostgreSQL is not running the hardened DriveMPVD image.\n' >&2
  exit 1
}
docker image inspect "$restore_image" >/dev/null

printf 'Stopping write-serving containers for a coordinated snapshot.\n'
services_stopped=true
"${compose[@]}" stop "${write_services[@]}" >/dev/null

docker exec "$postgres_id" sh -c \
  'pg_dump --format=custom --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  >"$backup_root/database.dump"
tar --acls --xattrs --numeric-owner -cpf "$backup_root/storage.tar" \
  -C "$storage_path" .
sha256sum "$backup_root/database.dump" "$backup_root/storage.tar" \
  >"$backup_root/SHA256SUMS"
chmod 0600 "$backup_root/database.dump" "$backup_root/storage.tar" \
  "$backup_root/SHA256SUMS"

"${compose[@]}" up -d --wait "${write_services[@]}" >/dev/null
services_stopped=false
printf 'Write-serving containers are healthy again.\n'

(
  cd "$backup_root"
  sha256sum --check SHA256SUMS
)
docker run --detach --name "$restore_container" \
  --read-only \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  --env POSTGRES_PASSWORD="$restore_password" \
  --mount "type=bind,src=$backup_root/database.dump,dst=/tmp/database.dump,readonly" \
  --tmpfs /var/lib/postgresql/data:rw,nosuid,nodev,size=1g,uid=70,gid=70,mode=0700 \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m,uid=70,gid=70,mode=1777 \
  --tmpfs /run/postgresql:rw,nosuid,nodev,size=1m,uid=70,gid=70,mode=3777 \
  "$restore_image" >/dev/null

ready=false
for _ in $(seq 1 60); do
  if docker exec "$restore_container" pg_isready -U postgres >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == "true" ]] || {
  docker logs "$restore_container" >&2
  printf 'Disposable restore database did not become ready.\n' >&2
  exit 1
}

docker exec -u 0 "$restore_container" pg_restore --list /tmp/database.dump >/dev/null
docker exec -u 0 "$restore_container" pg_restore --exit-on-error --no-owner --no-acl \
  -U postgres -d postgres /tmp/database.dump

source_head=$(docker exec "$postgres_id" sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT version_num FROM alembic_version"')
restored_head=$(docker exec "$restore_container" psql -U postgres -d postgres -Atc \
  'SELECT version_num FROM alembic_version')
[[ "$source_head" == "$restored_head" ]] || {
  printf 'Restored migration head does not match the source snapshot.\n' >&2
  exit 1
}

install -d -m 0700 "$restore_root/storage"
tar --acls --xattrs --numeric-owner -xpf "$backup_root/storage.tar" \
  -C "$restore_root/storage"

printf 'Backup and isolated restore drill completed: %s (migration %s).\n' \
  "$backup_root" "$restored_head"
