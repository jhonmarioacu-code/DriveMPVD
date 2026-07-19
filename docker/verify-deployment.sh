#!/usr/bin/env sh
# Run an authenticated deployment smoke test after creating the sole admin.
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repository_root"

environment_file=${DRIVEMPVD_COMPOSE_ENV_FILE:-docker/.env}
smoke_username=${DRIVEMPVD_SMOKE_USERNAME:?Set DRIVEMPVD_SMOKE_USERNAME}
smoke_password=${DRIVEMPVD_SMOKE_PASSWORD:?Set DRIVEMPVD_SMOKE_PASSWORD}
http_port=${DRIVEMPVD_HTTP_PORT:-8080}
base_url=${DRIVEMPVD_SMOKE_BASE_URL:-http://127.0.0.1:${http_port}}
csrf_cookie_name=${VITE_CSRF_COOKIE_NAME:-drivempvd_csrf}

cookies=$(mktemp)
payload=$(mktemp)
downloaded=$(mktemp)
range_body=$(mktemp)
range_headers=$(mktemp)
expected_range=$(mktemp)

cleanup() {
  rm -f "$cookies" "$payload" "$downloaded" "$range_body" "$range_headers" "$expected_range"
}
trap cleanup EXIT INT TERM

json_value() {
  python3 -c '
import json
import sys

value = json.load(sys.stdin)
for key in sys.argv[1].split("."):
    value = value[key]
print(value)
' "$1"
}

if [ "${1:-}" = "--start" ]; then
  docker compose --env-file "$environment_file" -f compose.yaml config >/dev/null
  docker compose --env-file "$environment_file" -f compose.yaml up --build --wait -d
fi

curl --fail --silent --show-error "$base_url/api/v1/ready" >/dev/null
curl --fail --silent --show-error "$base_url/" | grep -q '<div id="root">'

login_payload=$(python3 -c '
import json
import sys
print(json.dumps({"username": sys.argv[1], "password": sys.argv[2], "delivery": "cookie"}))
' "$smoke_username" "$smoke_password")

curl --fail --silent --show-error \
  --cookie-jar "$cookies" \
  --header 'Content-Type: application/json' \
  --data "$login_payload" \
  "$base_url/api/v1/auth/login" >/dev/null

csrf_token=$(awk -v cookie_name="$csrf_cookie_name" '$6 == cookie_name { print $7; exit }' "$cookies")
if [ -z "$csrf_token" ]; then
  echo "The login response did not set the configured CSRF cookie." >&2
  exit 1
fi

navigation=$(curl --fail --silent --show-error --cookie "$cookies" "$base_url/api/v1/storage/navigation")
root_id=$(printf '%s' "$navigation" | json_value 'data.folder.id')

printf 'phase-8 deployment smoke test\n' > "$payload"
payload_size=$(wc -c < "$payload" | tr -d ' ')
start_payload=$(printf '{"parent_id":"%s","filename":"phase-8-smoke.txt","size":%s,"mime_type":"text/plain"}' "$root_id" "$payload_size")
upload=$(curl --fail --silent --show-error \
  --cookie "$cookies" \
  --cookie-jar "$cookies" \
  --header "X-CSRF-Token: $csrf_token" \
  --header 'Content-Type: application/json' \
  --data "$start_payload" \
  "$base_url/api/v1/storage/uploads")
upload_id=$(printf '%s' "$upload" | json_value 'data.id')

curl --fail --silent --show-error \
  --cookie "$cookies" \
  --cookie-jar "$cookies" \
  --header "X-CSRF-Token: $csrf_token" \
  --header 'Content-Type: application/offset+octet-stream' \
  --header 'Upload-Offset: 0' \
  --request PATCH \
  --data-binary "@$payload" \
  "$base_url/api/v1/storage/uploads/$upload_id" >/dev/null

completed=$(curl --fail --silent --show-error \
  --cookie "$cookies" \
  --cookie-jar "$cookies" \
  --header "X-CSRF-Token: $csrf_token" \
  --request POST \
  "$base_url/api/v1/storage/uploads/$upload_id/complete")
file_id=$(printf '%s' "$completed" | json_value 'data.id')

curl --fail --silent --show-error \
  --cookie "$cookies" \
  --output "$downloaded" \
  "$base_url/api/v1/storage/files/$file_id/content"
cmp -s "$payload" "$downloaded"

curl --fail --silent --show-error \
  --cookie "$cookies" \
  --header 'Range: bytes=0-3' \
  --dump-header "$range_headers" \
  --output "$range_body" \
  "$base_url/api/v1/storage/files/$file_id/content"
grep -Eq '^HTTP/[0-9.]+ 206' "$range_headers"
head -c 4 "$payload" > "$expected_range"
cmp -s "$expected_range" "$range_body"

curl --fail --silent --show-error --head "$base_url/api/v1/health" \
  | grep -qi '^X-Content-Type-Options: nosniff'

printf '%s\n' "Deployment smoke test completed successfully for $base_url."
