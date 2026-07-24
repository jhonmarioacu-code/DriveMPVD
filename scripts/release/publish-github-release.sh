#!/usr/bin/env bash
# Publish an already-created Git tag through the authenticated GitHub CLI.
set -Eeuo pipefail

repository_root=$(cd -- "$(dirname -- "$BASH_SOURCE")/../.." && pwd)
[[ $# -eq 1 && -n "$1" ]] || {
  printf 'Usage: scripts/release/publish-github-release.sh <existing-tag>\n' >&2
  exit 2
}
tag=$1

command -v git >/dev/null 2>&1 || { printf 'Git is required.\n' >&2; exit 1; }
command -v gh >/dev/null 2>&1 || { printf 'GitHub CLI (gh) is required.\n' >&2; exit 1; }
git -C "$repository_root" diff --quiet
git -C "$repository_root" diff --cached --quiet
git -C "$repository_root" show-ref --verify --quiet "refs/tags/$tag" || {
  printf 'The requested release tag does not exist locally.\n' >&2
  exit 1
}
cd "$repository_root"
gh release create "$tag" --verify-tag --generate-notes
