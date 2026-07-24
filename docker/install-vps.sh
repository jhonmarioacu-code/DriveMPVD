#!/usr/bin/env bash
# Provision and deploy DriveMPVD on a fresh Ubuntu Server 24.04 VPS.
set -Eeuo pipefail

umask 077

mode="production"
install_dir="/srv/drivempvd"
repository_url=""
release_ref=""
release_commit=""
release_reference=""
domain=""
email=""
admin_user="admin"
ssh_port="22"
skip_admin="false"
skip_smoke="false"
skip_system_update="false"
skip_dns_check="false"
smoke_password_file=""
environment_dir="/etc/drivempvd"
environment_file=""
legacy_environment_file=""
configuration_source_file=""

usage() {
  cat <<'EOF'
Usage:
  sudo bash docker/install-vps.sh [options]

Modes:
  --mode production       HTTPS deployment; requires --domain and --email (default)
  --mode validation       HTTP deployment bound only to 127.0.0.1

Source:
  --repository URL        Clone/update this Git repository into --install-dir
  --release REF           Immutable Git tag/commit or release identifier
  --install-dir PATH      Deployment checkout (default: /srv/drivempvd)

Production:
  --domain NAME           DNS name that resolves to this VPS
  --email ADDRESS         Certbot account and expiry-notification email
  --skip-dns-check        Do not compare the domain A record with the public IP

Bootstrap and validation:
  --admin-user NAME       Singleton administrator username (default: admin)
  --skip-admin            Do not create the initial administrator
  --smoke-password-file PATH
                          Existing administrator password for the smoke test
  --skip-smoke            Do not run the authenticated deployment smoke test

Host:
  --ssh-port PORT         Preserve this SSH port in UFW (default: 22)
  --skip-system-update    Install requirements without apt-get upgrade
  -h, --help              Show this help

For a checkout already at /srv/drivempvd:
  sudo bash docker/install-vps.sh --mode validation --release 2026.07.19-vps

For a fresh production VPS from a Git release:
  curl -fsSL https://example.invalid/install-vps.sh | sudo bash -s -- \
    --repository https://example.invalid/DriveMPVD.git --release v1.0.0 \
    --domain drive.example.com --email ops@example.com
EOF
}

die() {
  printf 'DriveMPVD installer error: %s\n' "$*" >&2
  exit 1
}

log() {
  printf '\n==> %s\n' "$*"
}

require_value() {
  local option=$1
  local value=${2:-}
  [[ -n "$value" ]] || die "$option requires a value"
}

while (($#)); do
  case "$1" in
    --mode)
      require_value "$1" "${2:-}"
      mode=$2
      shift 2
      ;;
    --install-dir)
      require_value "$1" "${2:-}"
      install_dir=$2
      shift 2
      ;;
    --repository)
      require_value "$1" "${2:-}"
      repository_url=$2
      shift 2
      ;;
    --release)
      require_value "$1" "${2:-}"
      release_ref=$2
      shift 2
      ;;
    --domain)
      require_value "$1" "${2:-}"
      domain=$2
      shift 2
      ;;
    --email)
      require_value "$1" "${2:-}"
      email=$2
      shift 2
      ;;
    --admin-user)
      require_value "$1" "${2:-}"
      admin_user=$2
      shift 2
      ;;
    --ssh-port)
      require_value "$1" "${2:-}"
      ssh_port=$2
      shift 2
      ;;
    --smoke-password-file)
      require_value "$1" "${2:-}"
      smoke_password_file=$2
      shift 2
      ;;
    --skip-admin)
      skip_admin="true"
      shift
      ;;
    --skip-smoke)
      skip_smoke="true"
      shift
      ;;
    --skip-system-update)
      skip_system_update="true"
      shift
      ;;
    --skip-dns-check)
      skip_dns_check="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[[ $EUID -eq 0 ]] || die "run this installer as root (for example, with sudo)"
[[ "$mode" == "production" || "$mode" == "validation" ]] || \
  die "--mode must be production or validation"
[[ "$install_dir" == /* ]] || die "--install-dir must be an absolute path"
[[ "$ssh_port" =~ ^[0-9]+$ ]] && ((ssh_port >= 1 && ssh_port <= 65535)) || \
  die "--ssh-port must be between 1 and 65535"
[[ "$admin_user" =~ ^[A-Za-z0-9._-]{1,100}$ ]] || \
  die "--admin-user contains unsupported characters"

if [[ "$mode" == "production" ]]; then
  [[ "$domain" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] || \
    die "--domain must be a valid DNS hostname"
  [[ "$email" =~ ^[^[:space:]@]+@[^[:space:]@]+$ ]] || \
    die "--email must be a valid address"
fi

source /etc/os-release
[[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]] || \
  die "Ubuntu Server 24.04 LTS is required"

operator=${SUDO_USER:-root}
if ! id "$operator" >/dev/null 2>&1; then
  operator="root"
fi
operator_group=$(id -gn "$operator")

log "Updating Ubuntu and installing host requirements"
export DEBIAN_FRONTEND=noninteractive
if [[ "$skip_system_update" != "true" ]]; then
  apt-get update
  apt-get upgrade -y
fi
apt-get install -y \
  ca-certificates certbot curl docker-buildx docker-compose-v2 docker.io git openssl \
  python3 rsync ufw unattended-upgrades
systemctl enable --now docker
if [[ "$operator" != "root" ]]; then
  usermod -aG docker "$operator"
fi

log "Configuring the host firewall"
ufw default deny incoming
ufw default allow outgoing
ufw allow "${ssh_port}/tcp"
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

script_path=${BASH_SOURCE[0]:-}
script_root=""
if [[ -n "$script_path" && -f "$script_path" ]]; then
  script_root=$(cd -- "$(dirname -- "$script_path")/.." && pwd)
fi

log "Preparing the application release"
if [[ -n "$repository_url" ]]; then
  if [[ -d "$install_dir/.git" ]]; then
    git config --global --add safe.directory "$install_dir"
    git -C "$install_dir" fetch --tags --prune origin
  elif [[ -e "$install_dir" ]] && [[ -n "$(find "$install_dir" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    die "$install_dir exists and is not an empty Git checkout"
  else
    install -d -m 0750 "$install_dir"
    git clone "$repository_url" "$install_dir"
    git config --global --add safe.directory "$install_dir"
  fi
  if [[ -n "$release_ref" ]]; then
    release_reference=$release_ref
    release_commit=$(git -C "$install_dir" rev-parse --verify "${release_ref}^{commit}") || \
      die "--release does not resolve to a Git commit"
    if [[ "$mode" == "production" && ! "$release_ref" =~ ^[0-9a-fA-F]{40}$ ]]; then
      git -C "$install_dir" show-ref --verify --quiet "refs/tags/$release_ref" || \
        die "production --release must be a full commit SHA or an existing Git tag"
    fi
    git -C "$install_dir" checkout --detach "$release_commit"
  else
    [[ "$mode" == "validation" ]] || \
      die "production installation from Git requires --release"
    git -C "$install_dir" pull --ff-only
    release_commit=$(git -C "$install_dir" rev-parse --verify HEAD)
    release_reference=$release_commit
  fi
  if [[ "$mode" == "production" ]] && \
    [[ -n "$(git -C "$install_dir" status --porcelain --untracked-files=all)" ]]; then
    die "production checkout must be clean after resolving the release"
  fi
  repository_root=$install_dir
else
  [[ -n "$script_root" && -f "$script_root/compose.yaml" ]] || \
    die "run the script from a DriveMPVD checkout or provide --repository"
  repository_root=$script_root
  [[ "$repository_root" == "$install_dir" ]] || \
    die "the current checkout must be at --install-dir ($install_dir)"
  [[ "$mode" != "production" ]] || \
    die "production installation requires --repository and an immutable --release"
  if [[ -d "$repository_root/.git" ]]; then
    git -C "$repository_root" diff --quiet || \
      die "validation checkout has tracked working-tree changes"
    git -C "$repository_root" diff --cached --quiet || \
      die "validation checkout has staged changes"
    release_commit=$(git -C "$repository_root" rev-parse --verify HEAD)
    release_reference=${release_ref:-$release_commit}
  fi
fi

[[ -f "$repository_root/compose.yaml" ]] || die "compose.yaml is missing"
[[ -f "$repository_root/docker/.env.production.example" ]] || \
  die "the production environment template is missing"

if [[ -z "$release_commit" ]]; then
  [[ -n "$release_ref" ]] || die "--release is required for an archive checkout"
  release_commit="archive-$release_ref"
  release_reference=$release_ref
fi
image_tag=${release_commit//\//-}
[[ "$image_tag" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || \
  die "--release cannot be converted to a valid image tag"
case "${image_tag,,}" in
  local|latest|dev|development|edge|main|master|nightly|stable)
    die "--release must identify an immutable release"
    ;;
esac

chown -R "$operator:$operator_group" "$repository_root"
# A checkout can arrive from an archive or a Windows/SCP transfer with permissive
# modes.  Docker only needs to read the build context; only the deployment
# operator must be able to modify it.
chmod -R go-w -- "$repository_root"
install -d -m 0750 -o 10001 -g 10001 /data/storage
install -d -m 0750 /var/lib/drivempvd/acme-webroot
install -d -m 0750 -o root -g 101 /etc/drivempvd/tls
install -d -m 0750 /var/lib/drivempvd
install -d -m 0750 -o root -g root "$environment_dir"

environment_file="$environment_dir/${mode}.env"
legacy_environment_file="$repository_root/docker/.env"
configuration_source_file="$environment_file"
if [[ ! -f "$configuration_source_file" && -f "$legacy_environment_file" ]]; then
  configuration_source_file="$legacy_environment_file"
fi

env_value() {
  local key=$1
  local file=$2
  awk -F= -v key="$key" '
    $1 == key {
      value = substr($0, index($0, "=") + 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      if (value ~ /^".*"$/ || value ~ /^\047.*\047$/) {
        value = substr(value, 2, length(value) - 2)
      }
      print value
      exit
    }
  ' "$file"
}

existing_or_random_secret() {
  local key=$1
  local value=""
  if [[ -f "$configuration_source_file" ]]; then
    value=$(env_value "$key" "$configuration_source_file")
  fi
  if ((${#value} < 32)) || [[ "${value,,}" == *replace-* ]]; then
    value=$(openssl rand -hex 48)
  fi
  printf '%s' "$value"
}

postgres_password=$(existing_or_random_secret POSTGRES_PASSWORD)
access_secret=$(existing_or_random_secret DRIVEMPVD_JWT_ACCESS_SECRET)
refresh_secret=$(existing_or_random_secret DRIVEMPVD_JWT_REFRESH_SECRET)
pepper=$(existing_or_random_secret DRIVEMPVD_AUTH_SECRET_PEPPER)
database_url=""
if [[ -f "$configuration_source_file" ]]; then
  existing_postgres_password=$(env_value POSTGRES_PASSWORD "$configuration_source_file")
  if [[ "$existing_postgres_password" == "$postgres_password" ]]; then
    database_url=$(env_value DRIVEMPVD_DATABASE_URL "$configuration_source_file")
  fi
fi
if [[ -z "$database_url" ]]; then
  database_url="postgresql+asyncpg://drivempvd:${postgres_password}@postgres:5432/drivempvd"
fi

if [[ "$mode" == "production" ]]; then
  app_environment="production"
  docs_enabled="false"
  cookie_secure="true"
  tls_enabled="true"
  http_port="80"
  https_port="443"
  api_workers="2"
  postgres_memory_limit="4g"
  postgres_memory_reservation="1g"
  postgres_cpu_limit="1.25"
  api_memory_limit="2g"
  api_memory_reservation="512m"
  api_cpu_limit="2.0"
  worker_memory_limit="512m"
  worker_memory_reservation="128m"
  worker_cpu_limit="0.5"
  frontend_memory_limit="256m"
  frontend_memory_reservation="64m"
  frontend_cpu_limit="0.25"
  nginx_memory_limit="512m"
  nginx_memory_reservation="128m"
  nginx_cpu_limit="0.5"
else
  app_environment="development"
  docs_enabled="true"
  cookie_secure="false"
  tls_enabled="false"
  # Compose expands this into host_ip:host_port:container_port. It prevents a
  # validation deployment from becoming reachable over the public interface.
  http_port="127.0.0.1:8080"
  https_port="127.0.0.1:8443"
  api_workers="1"
  postgres_memory_limit="1g"
  postgres_memory_reservation="256m"
  postgres_cpu_limit="0.75"
  api_memory_limit="1g"
  api_memory_reservation="256m"
  api_cpu_limit="1.0"
  worker_memory_limit="256m"
  worker_memory_reservation="64m"
  worker_cpu_limit="0.25"
  frontend_memory_limit="128m"
  frontend_memory_reservation="32m"
  frontend_cpu_limit="0.25"
  nginx_memory_limit="256m"
  nginx_memory_reservation="64m"
  nginx_cpu_limit="0.5"
fi

release_manifest="$environment_dir/release.env"
release_manifest_tmp=$(mktemp "$release_manifest.XXXXXX")
cat >"$release_manifest_tmp" <<EOF
DRIVEMPVD_RELEASE_REFERENCE=$release_reference
DRIVEMPVD_RELEASE_COMMIT=$release_commit
DRIVEMPVD_RELEASE_INSTALLED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
chmod 0640 "$release_manifest_tmp"
chown root:root "$release_manifest_tmp"
mv -f "$release_manifest_tmp" "$release_manifest"

log "Writing a secret-safe deployment environment outside the checkout"
environment_tmp=$(mktemp "$environment_file.XXXXXX")
trap 'rm -f "${environment_tmp:-}"' EXIT
cat >"$environment_tmp" <<EOF
COMPOSE_PROJECT_NAME=drivempvd
DRIVEMPVD_COMPOSE_ENV_FILE=$environment_file
DRIVEMPVD_IMAGE_TAG=$image_tag

POSTGRES_DB=drivempvd
POSTGRES_USER=drivempvd
POSTGRES_PASSWORD=$postgres_password
DRIVEMPVD_DATABASE_URL=$database_url

DRIVEMPVD_APP_NAME=DriveMPVD
DRIVEMPVD_APP_VERSION=0.1.0
DRIVEMPVD_ENVIRONMENT=$app_environment
DRIVEMPVD_LOG_LEVEL=INFO
DRIVEMPVD_DOCS_ENABLED=$docs_enabled
DRIVEMPVD_STORAGE_ROOT=/data/storage
DRIVEMPVD_STORAGE_PATH=/data/storage
DRIVEMPVD_STORAGE_STREAM_BLOCK_SIZE_BYTES=1048576
DRIVEMPVD_STORAGE_WRITE_BUFFER_SIZE_BYTES=1048576
DRIVEMPVD_OUTBOX_WORKER_POLL_SECONDS=5
DRIVEMPVD_OUTBOX_WORKER_EVENT_BATCH_SIZE=32
DRIVEMPVD_OUTBOX_ORPHAN_SWEEP_BATCH_SIZE=100
DRIVEMPVD_MAX_UPLOAD_SIZE_BYTES=53687091200
DRIVEMPVD_MAX_UPLOAD_CHUNK_SIZE_BYTES=16777216

DRIVEMPVD_API_WORKERS=$api_workers
DRIVEMPVD_POSTGRES_INIT_MEMORY_LIMIT=128m
DRIVEMPVD_POSTGRES_INIT_MEMORY_RESERVATION=32m
DRIVEMPVD_POSTGRES_INIT_CPU_LIMIT=0.25
DRIVEMPVD_POSTGRES_INIT_PIDS_LIMIT=64
DRIVEMPVD_POSTGRES_MEMORY_LIMIT=$postgres_memory_limit
DRIVEMPVD_POSTGRES_MEMORY_RESERVATION=$postgres_memory_reservation
DRIVEMPVD_POSTGRES_CPU_LIMIT=$postgres_cpu_limit
DRIVEMPVD_POSTGRES_PIDS_LIMIT=256
DRIVEMPVD_MIGRATE_MEMORY_LIMIT=1g
DRIVEMPVD_MIGRATE_MEMORY_RESERVATION=256m
DRIVEMPVD_MIGRATE_CPU_LIMIT=1.0
DRIVEMPVD_MIGRATE_PIDS_LIMIT=256
DRIVEMPVD_API_MEMORY_LIMIT=$api_memory_limit
DRIVEMPVD_API_MEMORY_RESERVATION=$api_memory_reservation
DRIVEMPVD_API_CPU_LIMIT=$api_cpu_limit
DRIVEMPVD_API_PIDS_LIMIT=512
DRIVEMPVD_WORKER_MEMORY_LIMIT=$worker_memory_limit
DRIVEMPVD_WORKER_MEMORY_RESERVATION=$worker_memory_reservation
DRIVEMPVD_WORKER_CPU_LIMIT=$worker_cpu_limit
DRIVEMPVD_WORKER_PIDS_LIMIT=256
DRIVEMPVD_FRONTEND_MEMORY_LIMIT=$frontend_memory_limit
DRIVEMPVD_FRONTEND_MEMORY_RESERVATION=$frontend_memory_reservation
DRIVEMPVD_FRONTEND_CPU_LIMIT=$frontend_cpu_limit
DRIVEMPVD_FRONTEND_PIDS_LIMIT=128
DRIVEMPVD_NGINX_MEMORY_LIMIT=$nginx_memory_limit
DRIVEMPVD_NGINX_MEMORY_RESERVATION=$nginx_memory_reservation
DRIVEMPVD_NGINX_CPU_LIMIT=$nginx_cpu_limit
DRIVEMPVD_NGINX_PIDS_LIMIT=256

DRIVEMPVD_JWT_ACCESS_SECRET=$access_secret
DRIVEMPVD_JWT_REFRESH_SECRET=$refresh_secret
DRIVEMPVD_AUTH_SECRET_PEPPER=$pepper
DRIVEMPVD_AUTH_COOKIE_SECURE=$cookie_secure

VITE_API_BASE_URL=/api/v1
VITE_CSRF_COOKIE_NAME=drivempvd_csrf
VITE_CSRF_HEADER_NAME=X-CSRF-Token

DRIVEMPVD_HTTP_PORT=$http_port
DRIVEMPVD_HTTPS_PORT=$https_port
DRIVEMPVD_TLS_ENABLED=$tls_enabled
DRIVEMPVD_TLS_CERTIFICATES_PATH=/etc/drivempvd/tls
DRIVEMPVD_ACME_WEBROOT_PATH=/var/lib/drivempvd/acme-webroot
DRIVEMPVD_NGINX_CLIENT_MAX_BODY_SIZE=50g
EOF
chmod 0600 "$environment_tmp"
chown root:root "$environment_tmp"
mv -f "$environment_tmp" "$environment_file"
environment_tmp=""
export DRIVEMPVD_COMPOSE_ENV_FILE="$environment_file"
if [[ "$configuration_source_file" == "$legacy_environment_file" && \
  -f "$legacy_environment_file" ]]; then
  legacy_backup="$environment_dir/legacy-${mode}-$(date -u +%Y%m%dT%H%M%SZ).env"
  mv -- "$legacy_environment_file" "$legacy_backup"
  chmod 0600 "$legacy_backup"
  chown root:root "$legacy_backup"
  printf 'Migrated the legacy checkout environment to %s.\n' "$legacy_backup"
fi

if [[ "$mode" == "production" ]]; then
  if [[ "$skip_dns_check" != "true" ]]; then
    log "Checking that $domain resolves to this VPS"
    public_ip=$(curl -4fsS --max-time 10 https://api.ipify.org)
    getent ahostsv4 "$domain" | awk '{print $1}' | sort -u | \
      grep -Fqx "$public_ip" || \
      die "$domain does not resolve to this VPS public IPv4 address ($public_ip)"
  fi

  certificate_lineage="/etc/letsencrypt/live/$domain"
  if [[ ! -f "$certificate_lineage/fullchain.pem" || ! -f "$certificate_lineage/privkey.pem" ]]; then
    log "Requesting the initial TLS certificate for $domain"
    if ss -H -ltn 'sport = :80' | grep -q .; then
      die "TCP port 80 is already in use; it is required for initial certificate issuance"
    fi
    certbot certonly --standalone --non-interactive --agree-tos --no-eff-email \
      --domain "$domain" --email "$email"
  fi
  install -m 0644 "$(readlink -f "$certificate_lineage/fullchain.pem")" \
    /etc/drivempvd/tls/fullchain.pem
  install -m 0640 -o root -g 101 "$(readlink -f "$certificate_lineage/privkey.pem")" \
    /etc/drivempvd/tls/privkey.pem

  install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
  install -m 0755 "$repository_root/docker/certbot-deploy-hook.sh" \
    /etc/letsencrypt/renewal-hooks/deploy/drivempvd
  cat >/etc/drivempvd/deployment.conf <<EOF
REPOSITORY_ROOT=$repository_root
COMPOSE_ENV_FILE=$environment_file
TLS_TARGET=/etc/drivempvd/tls
EOF
  chmod 0600 /etc/drivempvd/deployment.conf

  log "Running the production preflight"
  python3 "$repository_root/docker/preflight.py" --env-file "$environment_file"
else
  log "Validating the loopback-only Compose configuration"
  docker compose --env-file "$environment_file" -f "$repository_root/compose.yaml" \
    config --quiet
fi

log "Building and starting DriveMPVD"
docker compose --env-file "$environment_file" -f "$repository_root/compose.yaml" \
  build postgres api frontend nginx
docker compose --env-file "$environment_file" -f "$repository_root/compose.yaml" \
  up --no-build --wait -d

if [[ "$mode" == "production" ]]; then
  log "Changing certificate renewal from standalone to the Nginx webroot"
  certbot reconfigure --cert-name "$domain" --webroot \
    --webroot-path /var/lib/drivempvd/acme-webroot --non-interactive
fi

admin_count=$(
  docker compose --env-file "$environment_file" -f "$repository_root/compose.yaml" \
    exec -T postgres sh -c \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT COUNT(*) FROM admin_accounts"' \
    | tr -d '[:space:]'
)

generated_password_file=""
if [[ "$admin_count" == "0" && "$skip_admin" != "true" ]]; then
  log "Creating the singleton administrator"
  if [[ -n "$smoke_password_file" ]]; then
    [[ -r "$smoke_password_file" ]] || die "the smoke password file is not readable"
    admin_password=$(<"$smoke_password_file")
  elif [[ -t 0 ]]; then
    read -r -s -p "Administrator password: " admin_password
    printf '\n'
    read -r -s -p "Confirm administrator password: " admin_confirmation
    printf '\n'
    [[ "$admin_password" == "$admin_confirmation" ]] || die "administrator passwords do not match"
    unset admin_confirmation
  else
    generated_password_file="/var/lib/drivempvd/initial-admin-password"
    admin_password=$(openssl rand -base64 30 | tr -d '\n')
    printf '%s' "$admin_password" >"$generated_password_file"
    chmod 0600 "$generated_password_file"
  fi
  ((${#admin_password} >= 12)) || die "administrator password must have at least 12 characters"
  printf '%s\n' "$admin_password" | \
    docker compose --env-file "$environment_file" -f "$repository_root/compose.yaml" \
      run --rm -T api python -m app.infrastructure.cli.create_admin \
        --password-stdin "$admin_user"
  if [[ -z "$smoke_password_file" ]]; then
    if [[ -n "$generated_password_file" ]]; then
      smoke_password_file=$generated_password_file
    else
      smoke_password_file=$(mktemp /run/drivempvd-smoke-password.XXXXXX)
      printf '%s' "$admin_password" >"$smoke_password_file"
      chmod 0600 "$smoke_password_file"
    fi
  fi
  unset admin_password
elif [[ "$admin_count" != "0" && -z "$smoke_password_file" ]]; then
  if [[ -r /var/lib/drivempvd/initial-admin-password ]]; then
    smoke_password_file=/var/lib/drivempvd/initial-admin-password
  fi
fi

if [[ "$skip_smoke" != "true" ]]; then
  if [[ -z "$smoke_password_file" ]]; then
    printf '%s\n' \
      "Smoke test skipped: provide --smoke-password-file for the existing administrator." >&2
  else
    [[ -r "$smoke_password_file" ]] || die "the smoke password file is not readable"
    log "Running the authenticated deployment smoke test"
    if [[ "$mode" == "production" ]]; then
      smoke_base_url="https://$domain"
    else
      smoke_base_url="http://127.0.0.1:8080"
    fi
    DRIVEMPVD_COMPOSE_ENV_FILE="$environment_file" \
    DRIVEMPVD_SMOKE_USERNAME="$admin_user" \
    DRIVEMPVD_SMOKE_PASSWORD_FILE="$smoke_password_file" \
    DRIVEMPVD_SMOKE_BASE_URL="$smoke_base_url" \
      sh "$repository_root/docker/verify-deployment.sh"
  fi
fi

case "$smoke_password_file" in
  /run/drivempvd-smoke-password.*)
    rm -f "$smoke_password_file"
    ;;
esac

log "Deployment status"
docker compose --env-file "$environment_file" -f "$repository_root/compose.yaml" ps
printf '\nDriveMPVD %s deployment completed.\n' "$mode"
if [[ -n "$generated_password_file" ]]; then
  printf 'Initial administrator password: retrieve it with sudo from %s and then delete it.\n' \
    "$generated_password_file"
fi
if [[ -f /var/run/reboot-required ]]; then
  printf 'Ubuntu reports that a reboot is required. Reboot after saving the credentials.\n'
fi
