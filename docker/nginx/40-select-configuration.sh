#!/bin/sh
set -eu

: "${DRIVEMPVD_NGINX_CLIENT_MAX_BODY_SIZE:=50g}"
export DRIVEMPVD_NGINX_CLIENT_MAX_BODY_SIZE

if [ "${DRIVEMPVD_ENVIRONMENT:-}" = "production" ]; then
  case "${DRIVEMPVD_TLS_ENABLED:-}" in
    true|TRUE|1|yes|YES) ;;
    *)
      echo "production requires DRIVEMPVD_TLS_ENABLED=true" >&2
      exit 1
      ;;
  esac
fi

case "${DRIVEMPVD_TLS_ENABLED:-false}" in
  true|TRUE|1|yes|YES)
    server_configuration=/etc/nginx/drivempvd/https.conf
    if [ ! -r /etc/nginx/tls/fullchain.pem ] || [ ! -r /etc/nginx/tls/privkey.pem ]; then
      echo "DRIVEMPVD_TLS_ENABLED requires /etc/nginx/tls/fullchain.pem and privkey.pem" >&2
      exit 1
    fi
    ;;
  false|FALSE|0|no|NO|"")
    server_configuration=/etc/nginx/drivempvd/http.conf
    ;;
  *)
    echo "DRIVEMPVD_TLS_ENABLED must be true or false" >&2
    exit 1
    ;;
esac

envsubst '${DRIVEMPVD_NGINX_CLIENT_MAX_BODY_SIZE}' \
  < /etc/nginx/drivempvd/nginx.conf.template \
  > /etc/nginx/nginx.conf
cp "$server_configuration" /etc/nginx/conf.d/default.conf
nginx -t
