#!/usr/bin/env sh
# Run the complete frontend quality, test, build, and dependency-security suite.
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
test_image="drivempvd-frontend-tests:host"

docker build --quiet --tag "$test_image" \
  --file "$repository_root/docker/frontend.test.Dockerfile" \
  "$repository_root" >/dev/null

docker run --rm "$test_image" sh -ec '
  npm run format
  npm run lint
  npm run typecheck
  npm test
  npm run build
  npm audit --audit-level=high
'

echo "Frontend host validation completed successfully."
