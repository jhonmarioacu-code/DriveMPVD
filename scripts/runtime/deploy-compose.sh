#!/usr/bin/env bash
# Promote an already checked-out release through the local Compose quality gates.
set -Eeuo pipefail

umask 077

[[ $EUID -eq 0 ]] || {
  printf 'Run this deployment gate as root so the protected environment is readable.\n' >&2
  exit 1
}

repository_root=$(cd -- "$(dirname -- "$BASH_SOURCE")/../.." && pwd)
environment_file=/etc/drivempvd/production.env
if [[ -v DRIVEMPVD_COMPOSE_ENV_FILE ]]; then
  environment_file=$DRIVEMPVD_COMPOSE_ENV_FILE
fi
skip_backup=false
skip_smoke=false

usage() {
  cat <<'EOF'
Usage: sudo scripts/runtime/deploy-compose.sh [--env-file PATH] [--skip-backup] [--skip-smoke]

The default environment is /etc/drivempvd/production.env. --skip-backup and
--skip-smoke are explicit exceptions that must be justified in the release log.
EOF
}

while (($#)); do
  case "$1" in
    --env-file)
      [[ $# -ge 2 && -n "$2" ]] || { printf '%s\n' '--env-file requires a value' >&2; exit 2; }
      environment_file=$2
      shift 2
      ;;
    --skip-backup)
      skip_backup=true
      shift
      ;;
    --skip-smoke)
      skip_smoke=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$environment_file" in
  /*) ;;
  *) environment_file="$repository_root/$environment_file" ;;
esac
[[ -r "$environment_file" ]] || {
  printf 'Compose environment is not readable: %s\n' "$environment_file" >&2
  exit 1
}
if [[ "$skip_smoke" != true ]] && {
  [[ ! -v DRIVEMPVD_SMOKE_USERNAME ]] || [[ ! -v DRIVEMPVD_SMOKE_PASSWORD_FILE ]]
}; then
  printf 'Set DRIVEMPVD_SMOKE_USERNAME and DRIVEMPVD_SMOKE_PASSWORD_FILE, or explicitly use --skip-smoke.\n' >&2
  exit 1
fi

export DRIVEMPVD_COMPOSE_ENV_FILE="$environment_file"
compose=(docker compose --env-file "$environment_file" -f "$repository_root/compose.yaml")
"${compose[@]}" config --quiet

if grep -Eq '^DRIVEMPVD_ENVIRONMENT=production$' "$environment_file"; then
  python3 "$repository_root/docker/preflight.py" --env-file "$environment_file"
fi

if [[ "$skip_backup" != true ]] && [[ -n "$("${compose[@]}" ps -q postgres)" ]]; then
  bash "$repository_root/docker/verify-backup-restore.sh"
fi

"${compose[@]}" build --pull postgres api frontend nginx
"${compose[@]}" up --no-build --wait -d
bash "$repository_root/docker/verify-container-images.sh"
if [[ "$skip_smoke" != true ]]; then
  sh "$repository_root/docker/verify-deployment.sh"
fi
"${compose[@]}" ps
