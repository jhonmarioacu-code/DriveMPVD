#!/usr/bin/env bash
# Stage a clean source tree by rsync; it never changes the active checkout.
set -Eeuo pipefail

umask 077

repository_root=$(cd -- "$(dirname -- "$BASH_SOURCE")/../.." && pwd)
target=""
apply=false
remote_releases=/srv/drivempvd/releases

usage() {
  cat <<'EOF'
Usage: scripts/transfer/push-rsync.sh --target user@host [--apply]

Without --apply the command only validates prerequisites. With --apply it
creates a new, hash-verified release directory under /srv/drivempvd/releases.
It never overwrites /srv/drivempvd or deploys the result.
EOF
}

while (($#)); do
  case "$1" in
    --target)
      [[ $# -ge 2 && -n "$2" ]] || { printf '%s\n' '--target requires a value' >&2; exit 2; }
      target=$2
      shift 2
      ;;
    --apply)
      apply=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ "$target" =~ ^[A-Za-z0-9._@:-]+$ ]] || {
  printf 'Use a simple SSH target user@host.\n' >&2
  exit 2
}
command -v git >/dev/null 2>&1 && command -v rsync >/dev/null 2>&1 || {
  printf 'Git and rsync are required.\n' >&2
  exit 1
}
git -C "$repository_root" diff --quiet
git -C "$repository_root" diff --cached --quiet
[[ -z "$(git -C "$repository_root" status --porcelain --untracked-files=all)" ]] || {
  printf 'Refuse to transfer a dirty checkout.\n' >&2
  exit 1
}
commit=$(git -C "$repository_root" rev-parse --verify HEAD)
stage="$remote_releases/$commit.incoming.$$"
final="$remote_releases/$commit"
exclude_args=(
  --exclude=.git/ --exclude=backend/.venv/ --exclude=backend/.mypy_cache/
  --exclude=backend/.pytest_cache/ --exclude=backend/.ruff_cache/
  --exclude=frontend/node_modules/ --exclude=frontend/dist/ --exclude=frontend/coverage/
  --exclude='**/__pycache__/' --exclude='*.pyc' --exclude=.coverage
  --exclude=.env --exclude=docker/.env --exclude='*.pem' --exclude='*.key'
)
if [[ "$apply" != true ]]; then
  printf 'Dry run only. Would stage commit %s on %s. Re-run with --apply to transfer.\n' "$commit" "$target"
  exit 0
fi

ssh -o StrictHostKeyChecking=yes "$target" \
  "set -eu; install -d -m 0750 '$remote_releases'; test ! -e '$final'; install -d -m 0750 '$stage'"
manifest=$(mktemp)
cleanup() {
  rm -f -- "$manifest"
}
trap cleanup EXIT INT TERM
(
  cd "$repository_root"
  find . -type f \
    ! -path './.git/*' ! -path './backend/.venv/*' ! -path './backend/.mypy_cache/*' \
    ! -path './backend/.pytest_cache/*' ! -path './backend/.ruff_cache/*' \
    ! -path './frontend/node_modules/*' ! -path './frontend/dist/*' ! -path './frontend/coverage/*' \
    ! -path '*/__pycache__/*' ! -name '*.pyc' ! -name '.coverage' ! -name '.env' \
    ! -path './docker/.env' ! -name '*.pem' ! -name '*.key' -print0 | sort -z | xargs -0 sha256sum
) >"$manifest"
rsync -a --delay-updates "${exclude_args[@]}" "$repository_root/" "$target:$stage/"
scp -o StrictHostKeyChecking=yes "$manifest" "$target:$stage/SHA256SUMS"
ssh -o StrictHostKeyChecking=yes "$target" \
  "set -eu; cd '$stage'; sha256sum --check SHA256SUMS; chmod -R go-w .; mv '$stage' '$final'; printf 'Staged %s\n' '$final'"
