#!/usr/bin/env bash
# Enable HTTPS for DriveMPVD using Let's Encrypt (Certbot).
#
# Prerequisites:
#   1. A domain (e.g. drive.example.com) pointing to this server's IP
#   2. Port 80 and 443 reachable from the internet
#   3. The server is running DriveMPVD on port 80/443 (DRIVEMPVD_HTTP_PORT=80)
#
# What this script does:
#   1. Validates the domain resolves to this server
#   2. Obtains TLS certificate via Certbot (webroot challenge)
#   3. Copies dereferenced PEM files (not symlinks) to DRIVEMPVD_TLS_CERTIFICATES_PATH
#   4. Updates docker/.env to enable TLS
#   5. Rebuilds and restarts the Nginx container
#   6. Installs a Certbot renewal cron hook
#
# Usage:
#   sudo bash scripts/runtime/enable-https.sh --domain drive.example.com --email ops@example.com
set -Eeuo pipefail
umask 077

[[ $EUID -eq 0 ]] || { printf 'Run as root.\n' >&2; exit 1; }

repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
environment_file="${repository_root}/docker/.env"
domain=""
email=""

usage() {
  cat <<'EOF'
Usage: sudo bash scripts/runtime/enable-https.sh --domain DOMAIN --email EMAIL [options]

Required:
  --domain NAME     DNS hostname that resolves to this server (e.g. drive.example.com)
  --email ADDRESS   Certbot account and renewal notification email

Options:
  --env-file PATH   Compose environment file (default: docker/.env)
  -h, --help        Show this help
EOF
}

while (($#)); do
  case "$1" in
    --domain)  domain="${2:?--domain requires a value}"; shift 2 ;;
    --email)   email="${2:?--email requires a value}";  shift 2 ;;
    --env-file) environment_file="${2:?}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 1 ;;
  esac
done

[[ -n "$domain" ]] || { printf 'Error: --domain is required\n' >&2; usage >&2; exit 1; }
[[ -n "$email"  ]] || { printf 'Error: --email is required\n'  >&2; usage >&2; exit 1; }

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

# ─── Validate domain resolves to this server ────────────────────────────────

log "Checking domain resolution for: $domain"
server_ip=$(curl -s --max-time 5 https://ipinfo.io/ip 2>/dev/null || \
            curl -s --max-time 5 https://api.ipify.org 2>/dev/null || \
            hostname -I | awk '{print $1}')
domain_ip=$(dig +short A "$domain" | tail -1)

if [[ "$server_ip" != "$domain_ip" ]]; then
  printf 'WARNING: Domain %s resolves to %s but this server IP is %s\n' \
    "$domain" "$domain_ip" "$server_ip" >&2
  printf 'If DNS is not yet propagated, wait and retry.\n' >&2
  read -r -p 'Continue anyway? [y/N] ' confirm
  [[ "$confirm" =~ ^[Yy]$ ]] || exit 1
else
  log "Domain resolves correctly: $domain -> $server_ip"
fi

# ─── Determine TLS certificates path from env ───────────────────────────────

tls_path=$(grep -E '^DRIVEMPVD_TLS_CERTIFICATES_PATH=' "$environment_file" \
  | cut -d= -f2 | tr -d '"' || true)
tls_path="${tls_path:-/etc/drivempvd/tls}"

install -d -m 0700 "$tls_path"

# ─── Obtain certificate via Certbot ─────────────────────────────────────────

acme_webroot=$(grep -E '^DRIVEMPVD_ACME_WEBROOT_PATH=' "$environment_file" \
  | cut -d= -f2 | tr -d '"' || true)
acme_webroot="${acme_webroot:-/var/lib/drivempvd/acme-webroot}"
install -d -m 0755 "$acme_webroot"

log "Obtaining Let's Encrypt certificate for $domain..."
certbot certonly \
  --webroot -w "$acme_webroot" \
  -d "$domain" \
  --email "$email" \
  --agree-tos \
  --non-interactive \
  --keep-until-expiring

# ─── Copy dereferenced PEM files (not symlinks) ─────────────────────────────

log "Copying dereferenced PEM files to $tls_path..."
cp --dereference "/etc/letsencrypt/live/${domain}/fullchain.pem" "${tls_path}/fullchain.pem"
cp --dereference "/etc/letsencrypt/live/${domain}/privkey.pem"   "${tls_path}/privkey.pem"
chmod 0600 "${tls_path}/privkey.pem"
chmod 0644 "${tls_path}/fullchain.pem"
log "Certificates installed at $tls_path"

# ─── Update .env to enable TLS ──────────────────────────────────────────────

log "Updating $environment_file to enable TLS..."
sed -i 's/^DRIVEMPVD_TLS_ENABLED=.*/DRIVEMPVD_TLS_ENABLED=true/'       "$environment_file"
sed -i 's/^DRIVEMPVD_HTTP_PORT=.*/DRIVEMPVD_HTTP_PORT=80/'             "$environment_file"
sed -i 's/^DRIVEMPVD_HTTPS_PORT=.*/DRIVEMPVD_HTTPS_PORT=443/'          "$environment_file"
sed -i 's/^DRIVEMPVD_AUTH_COOKIE_SECURE=.*/DRIVEMPVD_AUTH_COOKIE_SECURE=true/' "$environment_file"
sed -i 's/^DRIVEMPVD_ENVIRONMENT=.*/DRIVEMPVD_ENVIRONMENT=production/'  "$environment_file"
sed -i "s|^DRIVEMPVD_TLS_CERTIFICATES_PATH=.*|DRIVEMPVD_TLS_CERTIFICATES_PATH=${tls_path}|" "$environment_file"
log ".env updated."

# ─── Install Certbot renewal hook ───────────────────────────────────────────

deploy_hook="${repository_root}/docker/certbot-deploy-hook.sh"
if [[ -f "$deploy_hook" ]]; then
  log "Installing Certbot deploy hook..."
  cp "$deploy_hook" /etc/letsencrypt/renewal-hooks/deploy/drivempvd.sh
  chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/drivempvd.sh
  log "Deploy hook installed."
fi

# ─── Rebuild Nginx and restart ──────────────────────────────────────────────

log "Rebuilding Nginx container with TLS configuration..."
compose=(docker compose --env-file "$environment_file" -f "${repository_root}/compose.yaml")
"${compose[@]}" build nginx
"${compose[@]}" up -d nginx
log "Nginx restarted with HTTPS."

# ─── Verify ─────────────────────────────────────────────────────────────────

sleep 5
http_code=$(curl -sk -o /dev/null -w '%{http_code}' "https://127.0.0.1/api/v1/health" \
  --resolve "${domain}:443:127.0.0.1" 2>/dev/null || echo "000")

if [[ "$http_code" == "200" ]]; then
  log "HTTPS verified: https://${domain}/api/v1/health -> HTTP $http_code"
else
  printf 'WARNING: HTTPS check returned HTTP %s. Check nginx logs.\n' "$http_code" >&2
fi

log "HTTPS activation complete."
log "Your app is now available at: https://${domain}"
log ""
log "IMPORTANT: To fully test, also run:"
log "  bash scripts/runtime/health-check.sh --env-file $environment_file"
