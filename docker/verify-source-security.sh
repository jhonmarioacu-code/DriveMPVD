#!/usr/bin/env bash
# Scan the deployable source for high/critical secrets and misconfigurations.
set -Eeuo pipefail

[[ $EUID -eq 0 ]] || {
  printf 'Run the source security scan as root.\n' >&2
  exit 1
}

repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
scanner_image="aquasec/trivy:latest@sha256:cffe3f5161a47a6823fbd23d985795b3ed72a4c806da4c4df16266c02accdd6f"
install -d -m 0700 /var/lib/drivempvd
scan_root=$(mktemp -d /var/lib/drivempvd/source-security.XXXXXX)

cleanup() {
  case "$scan_root" in
    /var/lib/drivempvd/source-security.*) rm -rf -- "$scan_root" ;;
  esac
}
trap cleanup EXIT INT TERM

# Never copy runtime secrets, certificates, generated assets, or Git history
# into the scanner workspace. Examples remain scanned as part of the source.
tar \
  --exclude='./docker/.env' \
  --exclude='./.git' \
  --exclude='./frontend/node_modules' \
  --exclude='./frontend/dist' \
  --exclude='./docker/certificates' \
  --exclude='./docker/acme-webroot' \
  -C "$repository_root" -cf - . | tar -C "$scan_root" -xf -

scanner_log="$scan_root/trivy.log"
scanner_output="$scan_root/trivy.out"
if ! docker run --rm \
  -v "$scan_root:/workspace:ro" \
  "$scanner_image" fs \
    --scanners secret,misconfig \
    --severity HIGH,CRITICAL \
    --exit-code 1 \
    --no-progress \
    /workspace >"$scanner_output" 2>"$scanner_log"; then
  cat "$scanner_output" >&2
  cat "$scanner_log" >&2
  exit 1
fi

cat "$scanner_output"
printf 'Source secret and misconfiguration gate completed successfully.\n'
