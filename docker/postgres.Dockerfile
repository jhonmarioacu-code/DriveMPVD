# Build PostgreSQL from the Alpine 3.24 packages instead of inheriting the
# upstream PostgreSQL image. The upstream image contains a stale gosu binary
# in an inherited layer; scanners correctly retain that artifact even after it
# is removed. This image has no such layer and keeps PostgreSQL at 16.14.
FROM alpine:3.24.1@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b

RUN apk add --no-cache \
        postgresql16=16.14-r0 \
        postgresql16-client=16.14-r0 \
    && install -d -m 0700 -o postgres -g postgres /var/lib/postgresql/data \
    && install -d -m 3777 -o postgres -g postgres /run/postgresql

ENV PGDATA=/var/lib/postgresql/data/pgdata

COPY --chmod=0555 docker/postgres-entrypoint.sh /usr/local/bin/postgres-entrypoint.sh

USER postgres

ENTRYPOINT ["postgres-entrypoint.sh"]
CMD ["postgres"]
