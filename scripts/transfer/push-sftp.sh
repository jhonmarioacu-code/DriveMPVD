#!/usr/bin/env bash
# Stage a Git archive by batch SFTP; it never changes the active checkout.
set -Eeuo pipefail

umask 077

repository_root=$(cd -- "$(dirname -- "$BASH_SOURCE")/../.." && pwd)
target=""
apply=false
remote_releases=/srv/drivempvd/releases

usage() {
  cat <<'EOF'
Usage: scripts/transfer/push-sftp.sh --target user@host [--apply]

SFTP is an SSH-encrypted alternative when SCP is unavailable. It stages a Git
archive and does not modify the active deployment.
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
command -v git >/dev/null 2>&1 && command -v sftp >/dev/null 2>&1 || {
  printf 'Git and SFTP are required.\n' >&2
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
if [[ "$apply" != true ]]; then
  printf 'Dry run only. Would stage commit %s on %s. Re-run with --apply to transfer.\n' "$commit" "$target"
  exit 0
fi

archive=$(mktemp --suffix=.tar)
checksum=$(mktemp)
batch_file=$(mktemp)
cleanup() {
  rm -f -- "$archive" "$checksum" "$batch_file"
}
trap cleanup EXIT INT TERM
git -C "$repository_root" archive --format=tar "$commit" >"$archive"
(
  cd "$(dirname -- "$archive")"
  sha256sum "$(basename -- "$archive")"
) >"$checksum"
ssh -o StrictHostKeyChecking=yes "$target" \
  "set -eu; install -d -m 0750 '$remote_releases'; test ! -e '$final'; install -d -m 0750 '$stage'"
printf 'put %s %s/%s\nput %s %s/%s\n' \
  "$archive" "$stage" "$(basename -- "$archive")" \
  "$checksum" "$stage" "$(basename -- "$checksum")" >"$batch_file"
sftp -o StrictHostKeyChecking=yes -b "$batch_file" "$target"
remote_archive=$(basename -- "$archive")
remote_checksum=$(basename -- "$checksum")
ssh -o StrictHostKeyChecking=yes "$target" \
  "set -eu; cd '$stage'; sha256sum --check '$remote_checksum'; tar -tf '$remote_archive' >/dev/null; chmod -R go-w .; mv '$stage' '$final'; printf 'Staged %s\n' '$final'"
