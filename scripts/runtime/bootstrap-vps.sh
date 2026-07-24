#!/usr/bin/env bash
# Invoke the audited fresh-VPS installer from a checked-out DriveMPVD release.
set -Eeuo pipefail

repository_root=$(cd -- "$(dirname -- "$BASH_SOURCE")/../.." && pwd)
exec bash "$repository_root/docker/install-vps.sh" "$@"
