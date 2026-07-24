#!/bin/sh
# Initialise PostgreSQL with SCRAM authentication, then permanently drop root.
set -eu

case "${1:-}" in
    -*) set -- postgres "$@" ;;
esac

if [ "${1:-}" != "postgres" ]; then
    exec "$@"
fi

postgres_user=${POSTGRES_USER:-postgres}
postgres_database=${POSTGRES_DB:-$postgres_user}
postgres_data=${PGDATA:-/var/lib/postgresql/data}
postgres_root=/var/lib/postgresql/data

if [ "$postgres_data" != "$postgres_root/pgdata" ]; then
    printf 'PGDATA must be %s/pgdata.\n' "$postgres_root" >&2
    exit 1
fi

if [ ! -s "$postgres_data/PG_VERSION" ]; then
    : "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set before database initialization}"

    umask 077
    # initdb requires PGDATA to be empty. Store the one-time password file in
    # the private container tmpfs instead of the database directory.
    password_file=$(mktemp -p /tmp postgres-password.XXXXXX)
    cleanup() {
        rm -f -- "$password_file"
    }
    trap cleanup EXIT HUP INT TERM
    printf '%s\n' "$POSTGRES_PASSWORD" > "$password_file"

    initdb \
        --pgdata="$postgres_data" \
        --username="$postgres_user" \
        --pwfile="$password_file" \
        --auth-host=scram-sha-256 \
        --auth-local=trust

    # The database is reachable only from Docker's internal network. Permit
    # that network with SCRAM while keeping every TCP connection authenticated.
    cat >> "$postgres_data/postgresql.conf" <<'EOF'
listen_addresses = '*'
EOF
    cat >> "$postgres_data/pg_hba.conf" <<'EOF'
host    all             all             0.0.0.0/0               scram-sha-256
host    all             all             ::0/0                   scram-sha-256
EOF

    pg_ctl -D "$postgres_data" -o "-c listen_addresses=''" -w start
    if [ "$postgres_database" != "postgres" ]; then
        createdb --username="$postgres_user" "$postgres_database"
    fi
    pg_ctl -D "$postgres_data" -m fast -w stop
    cleanup
fi

exec "$@"
