#!/usr/bin/env bash
# Generate and activate a new administrator password without logging the secret.
set -Eeuo pipefail

umask 077

[[ $EUID -eq 0 ]] || {
  printf 'Run this password rotation as root.\n' >&2
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
username=${1:-admin}
password_file=${2:-/var/lib/drivempvd/initial-admin-password}
password_tmp=$(mktemp /var/lib/drivempvd/admin-password.XXXXXX)
password=""

cleanup() {
  rm -f -- "$password_tmp"
  unset password
}
trap cleanup EXIT INT TERM

[[ -r "$environment_file" ]] || {
  printf 'Compose environment is not readable: %s\n' "$environment_file" >&2
  exit 1
}

password=$(openssl rand -hex 24)
printf '%s' "$password" >"$password_tmp"
chmod 0600 "$password_tmp"

printf '%s\n' "$password" | \
  docker compose --env-file "$environment_file" -f "$repository_root/compose.yaml" \
    run --rm -T api python -m app.infrastructure.cli.change_admin_password \
      --password-stdin "$username"

mv -f "$password_tmp" "$password_file"
password_tmp=""
chmod 0600 "$password_file"
unset password

DRIVEMPVD_SMOKE_USERNAME="$username" \
DRIVEMPVD_SMOKE_PASSWORD_FILE="$password_file" \
  sh "$repository_root/docker/verify-deployment.sh"

printf 'Administrator password rotated and stored at %s.\n' "$password_file"
