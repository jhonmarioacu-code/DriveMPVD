#!/usr/bin/env sh
# Run the complete backend suite against an isolated disposable PostgreSQL 16.
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
suffix="$$"
network="drivempvd-host-tests-$suffix"
database_container="drivempvd-host-test-postgres-$suffix"
test_image="drivempvd-backend-tests:host"
database_image="drivempvd-postgres-tests:host"
test_password=$(openssl rand -hex 32)

cleanup() {
  docker rm -f "$database_container" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker network create "$network" >/dev/null
docker build --quiet --tag "$test_image" \
  --file "$repository_root/docker/backend.test.Dockerfile" \
  "$repository_root" >/dev/null
docker build --quiet --tag "$database_image" \
  --file "$repository_root/docker/postgres.Dockerfile" \
  "$repository_root" >/dev/null
docker run --detach --name "$database_container" \
  --network "$network" \
  --read-only \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  --env POSTGRES_DB=drivempvd_test \
  --env POSTGRES_USER=drivempvd_test \
  --env "POSTGRES_PASSWORD=$test_password" \
  --tmpfs /var/lib/postgresql/data:rw,nosuid,nodev,size=1g,uid=70,gid=70,mode=0700 \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m,uid=70,gid=70,mode=1777 \
  --tmpfs /run/postgresql:rw,nosuid,nodev,size=1m,uid=70,gid=70,mode=3777 \
  "$database_image" >/dev/null

ready=false
attempt=0
while [ "$attempt" -lt 60 ]; do
  if docker exec "$database_container" \
    pg_isready -U drivempvd_test -d drivempvd_test >/dev/null 2>&1; then
    ready=true
    break
  fi
  attempt=$((attempt + 1))
  sleep 1
done
[ "$ready" = true ] || {
  docker logs "$database_container" >&2
  echo "The isolated PostgreSQL test database did not become ready." >&2
  exit 1
}

docker run --rm \
  --network "$network" \
  --env "DRIVEMPVD_TEST_DATABASE_URL=postgresql+asyncpg://drivempvd_test:$test_password@$database_container:5432/drivempvd_test" \
  --env XDG_CACHE_HOME=/tmp \
  "$test_image" \
  sh -ec '
    python -m ruff check app tests
    python -m black --check app tests
    python -m mypy app tests
    python -m pytest
    python -m pip_audit -r requirements.lock
  '

echo "Backend PostgreSQL host validation completed successfully."
