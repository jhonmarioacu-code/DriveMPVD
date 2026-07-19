#!/usr/bin/env sh
# Run an authenticated, side-effect-cleaned deployment smoke test on Ubuntu.
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repository_root"

environment_file=${DRIVEMPVD_COMPOSE_ENV_FILE:-docker/.env}
if [ ! -r "$environment_file" ]; then
  echo "Compose environment file is not readable: $environment_file" >&2
  exit 1
fi

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

smoke_username=${DRIVEMPVD_SMOKE_USERNAME:?Set DRIVEMPVD_SMOKE_USERNAME}
configured_http_port=$(compose_env_value DRIVEMPVD_HTTP_PORT)
configured_tls_enabled=$(compose_env_value DRIVEMPVD_TLS_ENABLED)
http_port=${DRIVEMPVD_HTTP_PORT:-${configured_http_port:-8080}}
tls_enabled=${DRIVEMPVD_TLS_ENABLED:-${configured_tls_enabled:-false}}
if [ -n "${DRIVEMPVD_SMOKE_BASE_URL:-}" ]; then
  base_url=$DRIVEMPVD_SMOKE_BASE_URL
elif [ "$tls_enabled" = "true" ]; then
  echo "DRIVEMPVD_SMOKE_BASE_URL must be set to the certificate hostname for TLS." >&2
  exit 1
else
  base_url="http://127.0.0.1:${http_port}"
fi
csrf_cookie_name=${DRIVEMPVD_SMOKE_CSRF_COOKIE_NAME:-${VITE_CSRF_COOKIE_NAME:-drivempvd_csrf}}
access_cookie_name=${DRIVEMPVD_SMOKE_ACCESS_COOKIE_NAME:-drivempvd_access}
refresh_cookie_name=${DRIVEMPVD_SMOKE_REFRESH_COOKIE_NAME:-drivempvd_refresh}

if [ -n "${DRIVEMPVD_SMOKE_PASSWORD_FILE:-}" ]; then
  if [ ! -r "$DRIVEMPVD_SMOKE_PASSWORD_FILE" ]; then
    echo "DRIVEMPVD_SMOKE_PASSWORD_FILE is not readable." >&2
    exit 1
  fi
  smoke_password=$(cat "$DRIVEMPVD_SMOKE_PASSWORD_FILE")
elif [ -n "${DRIVEMPVD_SMOKE_PASSWORD:-}" ]; then
  smoke_password=$DRIVEMPVD_SMOKE_PASSWORD
  unset DRIVEMPVD_SMOKE_PASSWORD
elif [ -t 0 ]; then
  printf 'Administrator password: ' >&2
  stty -echo
  IFS= read -r smoke_password
  stty echo
  printf '\n' >&2
else
  echo "Set DRIVEMPVD_SMOKE_PASSWORD_FILE or DRIVEMPVD_SMOKE_PASSWORD." >&2
  exit 1
fi

umask 077
cookies=$(mktemp)
payload=$(mktemp)
downloaded=$(mktemp)
range_body=$(mktemp)
range_headers=$(mktemp)
head_headers=$(mktemp)
inline_headers=$(mktemp)
health_headers=$(mktemp)
login_headers=$(mktemp)
csrf_body=$(mktemp)
session_body=$(mktemp)
expected_range=$(mktemp)
login_password=$(mktemp)
login_payload=$(mktemp)
printf '%s' "$smoke_password" > "$login_password"
unset smoke_password
upload_id=
file_id=
folder_id=
csrf_token=

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

purge_entry() {
  entry_to_purge=${1:-}
  if [ -z "$entry_to_purge" ] || [ -z "${csrf_token:-}" ]; then
    return
  fi
  trashed=$(curl --silent --show-error \
    --cookie "$cookies" \
    --header "X-CSRF-Token: $csrf_token" \
    --request POST \
    "$base_url/api/v1/storage/entries/$entry_to_purge/trash" 2>/dev/null || true)
  trash_id=$(printf '%s' "$trashed" | json_value 'data.id' 2>/dev/null || true)
  if [ -n "$trash_id" ]; then
    curl --silent --show-error \
      --cookie "$cookies" \
      --header "X-CSRF-Token: $csrf_token" \
      --request DELETE \
      "$base_url/api/v1/storage/trash/$trash_id" >/dev/null 2>&1 || true
  fi
}

cleanup() {
  if [ -n "${file_id:-}" ]; then
    purge_entry "$file_id"
  fi
  if [ -n "${folder_id:-}" ]; then
    purge_entry "$folder_id"
  fi
  if [ -n "${upload_id:-}" ] && [ -z "${file_id:-}" ] && [ -n "${csrf_token:-}" ]; then
    curl --silent --show-error \
      --cookie "$cookies" \
      --header "X-CSRF-Token: $csrf_token" \
      --request DELETE \
      "$base_url/api/v1/storage/uploads/$upload_id" >/dev/null 2>&1 || true
  fi
  rm -f "$cookies" "$payload" "$downloaded" "$range_body" "$range_headers" \
    "$head_headers" "$inline_headers" "$health_headers" "$login_headers" \
    "$csrf_body" "$session_body" "$expected_range" "$login_password" \
    "$login_payload"
}
trap cleanup EXIT INT TERM

if [ "${1:-}" = "--start" ]; then
  docker compose --env-file "$environment_file" -f compose.yaml config --quiet
  docker compose --env-file "$environment_file" -f compose.yaml up --build --wait -d
fi

curl --fail --silent --show-error "$base_url/api/v1/ready" >/dev/null
curl --fail --silent --show-error "$base_url/" | grep -q '<div id="root">'
curl --fail --silent --show-error --dump-header "$health_headers" --output /dev/null \
  "$base_url/api/v1/health"
tr -d '\r' < "$health_headers" | grep -qi '^Content-Security-Policy:'
tr -d '\r' < "$health_headers" | grep -qi '^X-Content-Type-Options: nosniff$'
tr -d '\r' < "$health_headers" | grep -qi '^Referrer-Policy: no-referrer$'

python3 -c '
import json
import sys
password = sys.stdin.read().rstrip("\r\n")
print(json.dumps({"username": sys.argv[1], "password": password, "delivery": "cookie"}))
' "$smoke_username" < "$login_password" > "$login_payload"
rm -f "$login_password"

curl --fail --silent --show-error \
  --dump-header "$login_headers" \
  --cookie-jar "$cookies" \
  --header 'Content-Type: application/json' \
  --data-binary "@$login_payload" \
  "$base_url/api/v1/auth/login" >/dev/null
rm -f "$login_payload"

csrf_token=$(awk -v cookie_name="$csrf_cookie_name" '$6 == cookie_name { print $7; exit }' "$cookies")
if [ -z "$csrf_token" ]; then
  echo "The login response did not set the configured CSRF cookie." >&2
  exit 1
fi

tr -d '\r' < "$login_headers" | grep -i "^Set-Cookie: $access_cookie_name=" | \
  grep -qi 'HttpOnly'
tr -d '\r' < "$login_headers" | grep -i "^Set-Cookie: $access_cookie_name=" | \
  grep -qi 'SameSite=Lax'
tr -d '\r' < "$login_headers" | grep -i "^Set-Cookie: $access_cookie_name=" | \
  grep -qi 'Path=/'
tr -d '\r' < "$login_headers" | grep -i "^Set-Cookie: $refresh_cookie_name=" | \
  grep -qi 'HttpOnly'
tr -d '\r' < "$login_headers" | grep -i "^Set-Cookie: $refresh_cookie_name=" | \
  grep -qi 'SameSite=Strict'
tr -d '\r' < "$login_headers" | grep -i "^Set-Cookie: $refresh_cookie_name=" | \
  grep -qi 'Path=/api/v1/auth'
if tr -d '\r' < "$login_headers" | grep -i "^Set-Cookie: $csrf_cookie_name=" | \
  grep -qi 'HttpOnly'; then
  echo "The CSRF cookie must remain readable by the same-origin frontend." >&2
  exit 1
fi
tr -d '\r' < "$login_headers" | grep -i "^Set-Cookie: $csrf_cookie_name=" | \
  grep -qi 'SameSite=Lax'
tr -d '\r' < "$login_headers" | grep -i "^Set-Cookie: $csrf_cookie_name=" | \
  grep -qi 'Path=/'

case "$base_url" in
  https://*)
    tr -d '\r' < "$health_headers" | grep -qi '^Strict-Transport-Security:'
    for cookie_name in "$access_cookie_name" "$refresh_cookie_name" "$csrf_cookie_name"; do
      tr -d '\r' < "$login_headers" | grep -i "^Set-Cookie: $cookie_name=" | \
        grep -qi 'Secure'
    done
    ;;
esac

session=$(curl --fail --silent --show-error --cookie "$cookies" \
  "$base_url/api/v1/auth/session")
session_username=$(printf '%s' "$session" | json_value 'data.username')
[ "$session_username" = "$smoke_username" ]

# A state-changing request authenticated by a cookie must not work without CSRF.
csrf_status=$(curl --silent --show-error --output "$csrf_body" --write-out '%{http_code}' \
  --cookie "$cookies" \
  --request POST \
  "$base_url/api/v1/auth/logout" || true)
[ "$csrf_status" = '403' ]

navigation=$(curl --fail --silent --show-error --cookie "$cookies" \
  "$base_url/api/v1/storage/navigation")
root_id=$(printf '%s' "$navigation" | json_value 'data.folder.id')
entries=$(curl --fail --silent --show-error --cookie "$cookies" \
  "$base_url/api/v1/storage/folders/$root_id/entries?limit=50")
[ "$(printf '%s' "$entries" | json_value 'data.folder_id')" = "$root_id" ]

smoke_suffix="$(date +%s)-$$"
folder_name="phase-10-smoke-$smoke_suffix"
folder=$(curl --fail --silent --show-error \
  --cookie "$cookies" \
  --header "X-CSRF-Token: $csrf_token" \
  --header 'Content-Type: application/json' \
  --data "{\"parent_id\":\"$root_id\",\"name\":\"$folder_name\"}" \
  "$base_url/api/v1/storage/folders")
folder_id=$(printf '%s' "$folder" | json_value 'data.id')

renamed_folder_name="$folder_name-renamed"
curl --fail --silent --show-error \
  --cookie "$cookies" \
  --header "X-CSRF-Token: $csrf_token" \
  --header 'Content-Type: application/json' \
  --request PATCH \
  --data "{\"name\":\"$renamed_folder_name\"}" \
  "$base_url/api/v1/storage/entries/$folder_id" >/dev/null
folder_navigation=$(curl --fail --silent --show-error --cookie "$cookies" \
  "$base_url/api/v1/storage/navigation?folder_id=$folder_id")
[ "$(printf '%s' "$folder_navigation" | json_value 'data.folder.id')" = "$folder_id" ]

printf '%%PDF-1.7\nphase-10 deployment smoke test\n%%EOF\n' > "$payload"
payload_size=$(wc -c < "$payload" | tr -d ' ')
filename="phase-10-smoke-$smoke_suffix.pdf"
start_payload=$(printf '{"parent_id":"%s","filename":"%s","size":%s,"mime_type":"application/pdf"}' \
  "$root_id" "$filename" "$payload_size")
upload=$(curl --fail --silent --show-error \
  --cookie "$cookies" \
  --header "X-CSRF-Token: $csrf_token" \
  --header 'Content-Type: application/json' \
  --data "$start_payload" \
  "$base_url/api/v1/storage/uploads")
upload_id=$(printf '%s' "$upload" | json_value 'data.id')

curl --fail --silent --show-error --head --dump-header "$head_headers" --output /dev/null \
  --cookie "$cookies" \
  "$base_url/api/v1/storage/uploads/$upload_id"
tr -d '\r' < "$head_headers" | grep -qi '^Upload-Offset: 0$'

curl --fail --silent --show-error \
  --cookie "$cookies" \
  --header "X-CSRF-Token: $csrf_token" \
  --header 'Content-Type: application/offset+octet-stream' \
  --header 'Upload-Offset: 0' \
  --request PATCH \
  --data-binary "@$payload" \
  "$base_url/api/v1/storage/uploads/$upload_id" >/dev/null

completed=$(curl --fail --silent --show-error \
  --cookie "$cookies" \
  --header "X-CSRF-Token: $csrf_token" \
  --request POST \
  "$base_url/api/v1/storage/uploads/$upload_id/complete")
file_id=$(printf '%s' "$completed" | json_value 'data.id')
upload_id=

curl --fail --silent --show-error \
  --cookie "$cookies" \
  --header "X-CSRF-Token: $csrf_token" \
  --header 'Content-Type: application/json' \
  --request POST \
  --data "{\"destination_folder_id\":\"$folder_id\"}" \
  "$base_url/api/v1/storage/entries/$file_id/move" >/dev/null

folder_entries=$(curl --fail --silent --show-error --cookie "$cookies" \
  "$base_url/api/v1/storage/folders/$folder_id/entries?limit=50")
printf '%s' "$folder_entries" | python3 -c '
import json
import sys

file_id = sys.argv[1]
items = json.load(sys.stdin)["data"]["items"]
raise SystemExit(0 if any(item["id"] == file_id for item in items) else 1)
' "$file_id"

curl --fail --silent --show-error --head --dump-header "$head_headers" --output /dev/null \
  --cookie "$cookies" \
  "$base_url/api/v1/storage/files/$file_id/content"
tr -d '\r' < "$head_headers" | grep -qi '^Accept-Ranges: bytes$'
tr -d '\r' < "$head_headers" | grep -qi "^Content-Length: $payload_size$"
tr -d '\r' < "$head_headers" | grep -qi '^Content-Disposition: attachment;'

curl --fail --silent --show-error --head --dump-header "$inline_headers" --output /dev/null \
  --cookie "$cookies" \
  "$base_url/api/v1/storage/files/$file_id/content?disposition=inline"
tr -d '\r' < "$inline_headers" | grep -qi '^Content-Type: application/pdf'
tr -d '\r' < "$inline_headers" | grep -qi '^Content-Disposition: inline;'

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
tr -d '\r' < "$range_headers" | grep -Eq '^HTTP/[0-9.]+ 206'
head -c 4 "$payload" > "$expected_range"
cmp -s "$expected_range" "$range_body"

purge_entry "$file_id"
file_id=
purge_entry "$folder_id"
folder_id=

curl --fail --silent --show-error \
  --cookie "$cookies" \
  --cookie-jar "$cookies" \
  --header "X-CSRF-Token: $csrf_token" \
  --request POST \
  "$base_url/api/v1/auth/logout" >/dev/null
logout_status=$(curl --silent --show-error --output "$session_body" --write-out '%{http_code}' \
  --cookie "$cookies" "$base_url/api/v1/auth/session" || true)
[ "$logout_status" = '401' ]

printf '%s\n' "Deployment smoke test completed successfully for $base_url."
