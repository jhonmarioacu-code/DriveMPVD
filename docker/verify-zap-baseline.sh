#!/usr/bin/env bash
# Run a passive OWASP ZAP baseline scan against an explicitly selected HTTP(S)
# target. This is intended for an isolated candidate or a controlled release
# window; it does not authenticate or run active attack rules.
set -Eeuo pipefail

target=${DRIVEMPVD_ZAP_TARGET:-}
network=${DRIVEMPVD_ZAP_NETWORK:-host}
minutes=${DRIVEMPVD_ZAP_MINUTES:-1}
scanner_image="ghcr.io/zaproxy/zaproxy:stable@sha256:c558ee87358911ab17278c70991e856f57793e115d9cd0f88ca475cf82907a1a"

[[ "$target" =~ ^https?:// ]] || {
  printf 'Set DRIVEMPVD_ZAP_TARGET to an explicit http:// or https:// URL.\n' >&2
  exit 1
}
[[ "$minutes" =~ ^[1-9][0-9]*$ ]] || {
  printf 'DRIVEMPVD_ZAP_MINUTES must be a positive whole number.\n' >&2
  exit 1
}

report=$(mktemp)
cleanup() {
  rm -f -- "$report"
}
trap cleanup EXIT INT TERM

set +e
docker run --rm \
  --network "$network" \
  --memory=1g \
  --cpus=1.0 \
  --pids-limit=256 \
  "$scanner_image" \
  zap-baseline.py -t "$target" -m "$minutes" -I >"$report" 2>&1
status=$?
set -e

cat "$report"
case "$status" in
  0)
    printf 'OWASP ZAP baseline completed without fail-level alerts.\n'
    ;;
  1)
    printf 'OWASP ZAP reported at least one fail-level alert.\n' >&2
    exit 1
    ;;
  *)
    printf 'OWASP ZAP baseline failed with status %s.\n' "$status" >&2
    exit "$status"
    ;;
esac
