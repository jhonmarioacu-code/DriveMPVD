#!/usr/bin/env bash
# Copy dereferenced Certbot material and reload the running Nginx container.
set -Eeuo pipefail

config_file=/etc/drivempvd/deployment.conf
[[ -r "$config_file" ]] || {
  printf 'DriveMPVD Certbot hook: missing %s\n' "$config_file" >&2
  exit 1
}
[[ -n "${RENEWED_LINEAGE:-}" ]] || {
  printf 'DriveMPVD Certbot hook: RENEWED_LINEAGE is missing\n' >&2
  exit 1
}

config_value() {
  local key=$1
  awk -F= -v key="$key" '$1 == key {print substr($0, index($0, "=") + 1); exit}' \
    "$config_file"
}

repository_root=$(config_value REPOSITORY_ROOT)
environment_file=$(config_value COMPOSE_ENV_FILE)
tls_target=$(config_value TLS_TARGET)

[[ -f "$repository_root/compose.yaml" ]] || {
  printf 'DriveMPVD Certbot hook: compose.yaml is missing\n' >&2
  exit 1
}
[[ -f "$environment_file" ]] || {
  printf 'DriveMPVD Certbot hook: Compose environment is missing\n' >&2
  exit 1
}

install -d -m 0750 -o root -g 101 "$tls_target"
install -m 0644 "$(readlink -f "$RENEWED_LINEAGE/fullchain.pem")" \
  "$tls_target/fullchain.pem"
install -m 0640 -o root -g 101 "$(readlink -f "$RENEWED_LINEAGE/privkey.pem")" \
  "$tls_target/privkey.pem"

if docker compose --env-file "$environment_file" -f "$repository_root/compose.yaml" \
  ps --status running nginx | grep -q nginx; then
  docker compose --env-file "$environment_file" -f "$repository_root/compose.yaml" \
    exec -T nginx nginx -c /tmp/drivempvd-nginx/nginx.conf -s reload
fi
