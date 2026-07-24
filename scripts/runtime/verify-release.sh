#!/usr/bin/env bash
# Verify the running Compose release without printing secrets.
set -Eeuo pipefail

[[ $EUID -eq 0 ]] || {
  printf 'Run this verification as root so the protected environment is readable.\n' >&2
  exit 1
}

repository_root=$(cd -- "$(dirname -- "$BASH_SOURCE")/../.." && pwd)
environment_file=/etc/drivempvd/production.env
if [[ -v DRIVEMPVD_COMPOSE_ENV_FILE ]]; then
  environment_file=$DRIVEMPVD_COMPOSE_ENV_FILE
fi
case "$environment_file" in
  /*) ;;
  *) environment_file="$repository_root/$environment_file" ;;
esac
[[ -r "$environment_file" ]] || {
  printf 'Compose environment is not readable: %s\n' "$environment_file" >&2
  exit 1
}
export DRIVEMPVD_COMPOSE_ENV_FILE="$environment_file"
compose=(docker compose --env-file "$environment_file" -f "$repository_root/compose.yaml")

"${compose[@]}" config --quiet
for service in postgres api worker frontend nginx; do
  container=$("${compose[@]}" ps -q "$service")
  [[ -n "$container" ]] || {
    printf 'Service is missing: %s\n' "$service" >&2
    exit 1
  }
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$container")
  [[ "$health" == healthy ]] || {
    printf 'Service is not healthy: %s (%s)\n' "$service" "$health" >&2
    exit 1
  }
done

if "${compose[@]}" logs --since 15m --no-log-prefix nginx api worker postgres frontend | \
  grep -Eqi 'Traceback|CRITICAL|FATAL|Unhandled exception|panic'; then
  printf 'Critical pattern found in recent service logs.\n' >&2
  exit 1
fi

if [[ -v DRIVEMPVD_SMOKE_USERNAME && -v DRIVEMPVD_SMOKE_PASSWORD_FILE ]]; then
  sh "$repository_root/docker/verify-deployment.sh"
else
  printf 'Health and log verification passed; smoke skipped because no smoke credentials were supplied.\n'
fi
