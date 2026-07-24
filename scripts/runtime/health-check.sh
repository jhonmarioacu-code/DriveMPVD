#!/usr/bin/env bash
# Health check script for DriveMPVD.
# Verifies all Docker services are healthy and the API responds correctly.
# Suitable for use as a cron job or systemd timer.
#
# Exit codes:
#   0  All checks passed
#   1  One or more checks failed
#
# Usage:
#   sudo bash scripts/runtime/health-check.sh [--env-file PATH] [--notify-url URL]
#
# Example cron (every 5 minutes, alert via webhook):
#   */5 * * * * root bash /srv/drivempvd/scripts/runtime/health-check.sh \
#     --notify-url https://hc-ping.com/YOUR-UUID 2>&1 | logger -t drivempvd-health
set -Eeuo pipefail

umask 077

repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
environment_file="${repository_root}/docker/.env"
notify_url=""

usage() {
  cat <<'EOF'
Usage: bash scripts/runtime/health-check.sh [options]

Options:
  --env-file PATH     Compose environment file (default: docker/.env)
  --notify-url URL    Ping this URL on success (Healthchecks.io / UptimeRobot)
  -h, --help          Show this help
EOF
}

while (($#)); do
  case "$1" in
    --env-file)
      environment_file="${2:?--env-file requires a value}"
      shift 2
      ;;
    --notify-url)
      notify_url="${2:?--notify-url requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

# ─── Helpers ────────────────────────────────────────────────────────────────

failures=0
log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
fail() { log "FAIL: $*" >&2; ((failures++)); }
pass() { log "OK:   $*"; }

# ─── Resolve Compose env ────────────────────────────────────────────────────

if [[ ! -f "$environment_file" ]]; then
  fail "Environment file not found: $environment_file"
  exit 1
fi

# Read HTTP port from env file (default 9090 for non-TLS deployments)
http_port=$(grep -E '^DRIVEMPVD_HTTP_PORT=' "$environment_file" | cut -d= -f2 | tr -d '"' || true)
http_port="${http_port:-8080}"

compose_cmd=(docker compose --env-file "$environment_file" -f "${repository_root}/compose.yaml")

# ─── Check 1: All expected services are running and healthy ─────────────────

log "Checking Docker service health..."
expected_services=(postgres api worker frontend nginx)

for service in "${expected_services[@]}"; do
  container_id=$("${compose_cmd[@]}" ps -q "$service" 2>/dev/null || true)
  if [[ -z "$container_id" ]]; then
    fail "Service '$service' has no running container"
    continue
  fi

  status=$(docker inspect --format '{{.State.Status}}' "$container_id" 2>/dev/null || echo "unknown")
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$container_id" 2>/dev/null || echo "unknown")

  if [[ "$status" != "running" ]]; then
    fail "Service '$service' status=$status (expected: running)"
  elif [[ "$health" != "healthy" && "$health" != "no-healthcheck" ]]; then
    fail "Service '$service' health=$health (expected: healthy)"
  else
    pass "Service '$service' status=$status health=$health"
  fi
done

# ─── Check 2: API liveness ──────────────────────────────────────────────────

log "Checking API liveness endpoint..."
api_url="http://127.0.0.1:${http_port}/api/v1/health"
http_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$api_url" 2>/dev/null || echo "000")

if [[ "$http_code" == "200" ]]; then
  pass "API liveness: HTTP $http_code at $api_url"
else
  fail "API liveness: HTTP $http_code at $api_url (expected: 200)"
fi

# ─── Check 3: API readiness (database connectivity) ─────────────────────────

log "Checking API readiness endpoint..."
ready_url="http://127.0.0.1:${http_port}/api/v1/ready"
ready_response=$(curl -s --max-time 5 "$ready_url" 2>/dev/null || echo '{}')
ready_status=$(echo "$ready_response" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("data",{}).get("status",""))' 2>/dev/null || echo "")

if [[ "$ready_status" == "ready" ]]; then
  pass "API readiness: status=$ready_status"
else
  fail "API readiness: status='${ready_status}' (expected: ready)"
fi

# ─── Check 4: Storage directory accessible ──────────────────────────────────

log "Checking storage directory..."
storage_path=$(grep -E '^DRIVEMPVD_STORAGE_PATH=' "$environment_file" | cut -d= -f2 | tr -d '"' || true)
storage_path="${storage_path:-/data/storage}"

if [[ -d "$storage_path" ]]; then
  # Check there's at least 1 GB free on the storage partition
  available_kb=$(df -k "$storage_path" | awk 'NR==2{print $4}')
  available_gb=$(( available_kb / 1024 / 1024 ))
  if (( available_gb < 1 )); then
    fail "Storage partition has less than 1 GB free (${available_gb} GB available at ${storage_path})"
  else
    pass "Storage directory: ${storage_path} (${available_gb} GB free)"
  fi
else
  fail "Storage directory not found: $storage_path"
fi

# ─── Notify on success ──────────────────────────────────────────────────────

if (( failures == 0 )); then
  log "All health checks passed."
  if [[ -n "$notify_url" ]]; then
    curl -fsS --retry 3 --max-time 10 "$notify_url" > /dev/null 2>&1 || \
      log "WARNING: Failed to ping notify URL (non-fatal)"
    pass "Pinged monitoring URL"
  fi
  exit 0
else
  log "Health check FAILED: $failures check(s) did not pass."
  exit 1
fi
