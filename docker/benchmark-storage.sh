#!/usr/bin/env bash
# Run the local-storage benchmark in the same unprivileged Python image used by
# the backend suite. The target is an explicit disposable host directory, never
# the application storage mount.
set -Eeuo pipefail

[[ $EUID -eq 0 ]] || {
  printf 'Run the storage benchmark as root.\n' >&2
  exit 1
}

benchmark_dir=${DRIVEMPVD_STORAGE_BENCHMARK_DIR:-}
[[ "$benchmark_dir" = /* && "$benchmark_dir" != "/" ]] || {
  printf 'Set DRIVEMPVD_STORAGE_BENCHMARK_DIR to an absolute non-root path.\n' >&2
  exit 1
}

repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
test_image="drivempvd-storage-benchmark:host"
container_directory=/data/drivempvd-benchmark

install -d -m 0700 -o 10001 -g 10001 -- "$benchmark_dir"
ownership=$(stat -c '%u:%g' -- "$benchmark_dir")
[[ "$ownership" = "10001:10001" ]] || {
  printf 'Benchmark directory must be owned by UID:GID 10001:10001.\n' >&2
  exit 1
}

docker build --quiet --tag "$test_image" \
  --file "$repository_root/docker/backend.test.Dockerfile" \
  "$repository_root" >/dev/null

docker run --rm \
  --read-only \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --mount "type=bind,src=$benchmark_dir,dst=$container_directory" \
  "$test_image" \
  python scripts/benchmark_storage.py \
    --directory "$container_directory" \
    "$@"
