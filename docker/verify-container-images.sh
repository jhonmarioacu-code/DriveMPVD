#!/usr/bin/env bash
# Fail when a deployed image has a fixed HIGH or CRITICAL vulnerability.
set -Eeuo pipefail

[[ $EUID -eq 0 ]] || {
  printf 'Run the container image scan as root.\n' >&2
  exit 1
}

repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
environment_file=${DRIVEMPVD_COMPOSE_ENV_FILE:-"$repository_root/docker/.env"}
case "$environment_file" in
  /*) ;;
  *) environment_file="$repository_root/$environment_file" ;;
esac
export DRIVEMPVD_COMPOSE_ENV_FILE="$environment_file"
scanner_image="aquasec/trivy:latest@sha256:cffe3f5161a47a6823fbd23d985795b3ed72a4c806da4c4df16266c02accdd6f"
cache_root=/var/lib/drivempvd/trivy-cache
report_root=$(mktemp -d /var/lib/drivempvd/trivy-report.XXXXXX)

cleanup() {
  case "$report_root" in
    /var/lib/drivempvd/trivy-report.*) rm -rf -- "$report_root" ;;
  esac
}
trap cleanup EXIT INT TERM

[[ -r "$environment_file" ]] || {
  printf 'Compose environment is not readable: %s\n' "$environment_file" >&2
  exit 1
}

image_tag=${DRIVEMPVD_IMAGE_TAG:-}
if [[ -z "$image_tag" ]]; then
  image_tag=$(awk -F= '$1 == "DRIVEMPVD_IMAGE_TAG" { print $2; exit }' "$environment_file")
fi
[[ -n "$image_tag" ]] || {
  printf 'DRIVEMPVD_IMAGE_TAG is missing.\n' >&2
  exit 1
}
install -d -m 0700 "$cache_root"
images=(
  "drivempvd-api:$image_tag"
  "drivempvd-frontend:$image_tag"
  "drivempvd-nginx:$image_tag"
  "drivempvd-postgres:$image_tag"
)

total=0
for index in "${!images[@]}"; do
  image=${images[$index]}
  report="$report_root/report-$index.json"
  scanner_log="$report_root/scanner-$index.log"
  if ! docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$cache_root:/root/.cache/" \
    -v "$report_root:/report" \
    "$scanner_image" image \
      --scanners vuln \
      --severity HIGH,CRITICAL \
      --ignore-unfixed \
      --format json \
      --output "/report/report-$index.json" \
      --no-progress \
      "$image" > /dev/null 2>"$scanner_log"; then
    cat "$scanner_log" >&2
    exit 1
  fi
  findings=$(python3 - "$report" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as report_file:
    report = json.load(report_file)
print(
    sum(
        len(result.get("Vulnerabilities") or [])
        for result in report.get("Results", [])
    )
)
PY
  )
  printf '%s: %s fixed HIGH/CRITICAL vulnerabilities.\n' "$image" "$findings"
  total=$((total + findings))
done

((total == 0)) || {
  printf 'Container vulnerability gate failed with %s findings.\n' "$total" >&2
  exit 1
}
printf 'Container vulnerability gate completed successfully.\n'
