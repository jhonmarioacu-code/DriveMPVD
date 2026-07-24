#!/bin/sh
# Render the runtime configuration in /tmp, then run Nginx without root.
set -eu

/docker-entrypoint.d/40-select-configuration.sh

if [ "${1:-}" = "nginx" ]; then
    shift
    exec nginx -c /tmp/drivempvd-nginx/nginx.conf "$@"
fi

exec "$@"
