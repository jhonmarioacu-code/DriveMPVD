#!/usr/bin/env bash
# Create a traceable manifest for an immutable Git release without secrets.
set -Eeuo pipefail

umask 077

repository_root=$(cd -- "$(dirname -- "$BASH_SOURCE")/../.." && pwd)
reference="HEAD"
output_file=""
temporary_output=""
archive=""

usage() {
  cat <<'EOF'
Usage: scripts/release/prepare-release.sh [--ref <tag-or-full-sha>] [--output <file>]

The checkout must be clean. A tag is recorded as a reference and resolved to a
full commit SHA. The generated manifest contains no credentials. Unless
--output is supplied it is written outside the checkout under a private
temporary directory.
EOF
}

cleanup() {
  rm -f -- "$archive" "$temporary_output"
}
trap cleanup EXIT INT TERM

while (($#)); do
  case "$1" in
    --ref)
      [[ $# -ge 2 && -n "$2" ]] || { printf '%s\n' '--ref requires a value' >&2; exit 2; }
      reference=$2
      shift 2
      ;;
    --output)
      [[ $# -ge 2 && -n "$2" ]] || { printf '%s\n' '--output requires a value' >&2; exit 2; }
      output_file=$2
      shift 2
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

command -v git >/dev/null 2>&1 || {
  printf 'Git is required to prepare a release.\n' >&2
  exit 1
}
git -C "$repository_root" rev-parse --is-inside-work-tree >/dev/null
git -C "$repository_root" diff --quiet
git -C "$repository_root" diff --cached --quiet
[[ -z "$(git -C "$repository_root" status --porcelain --untracked-files=all)" ]] || {
  printf 'Refuse to prepare a release from a dirty checkout.\n' >&2
  exit 1
}

commit=$(git -C "$repository_root" rev-parse --verify "$reference^{commit}") || {
  printf 'Release reference does not resolve to a commit.\n' >&2
  exit 1
}
if [[ ! "$reference" =~ ^[0-9a-fA-F]{40}$ ]]; then
  git -C "$repository_root" show-ref --verify --quiet "refs/tags/$reference" || {
    printf 'Use a full commit SHA or an existing Git tag, never a branch.\n' >&2
    exit 1
  }
fi

archive=$(mktemp)
git -C "$repository_root" archive --format=tar "$commit" >"$archive"
archive_sha256=$(sha256sum "$archive" | awk '{print $1}')

if [[ -z "$output_file" ]]; then
  manifest_directory=/tmp/drivempvd-release-manifests
  if [[ -v TMPDIR && -n "$TMPDIR" ]]; then
    manifest_directory="$TMPDIR/drivempvd-release-manifests"
  fi
  install -d -m 0700 "$manifest_directory"
  output_file="$manifest_directory/release-$commit.env"
fi
case "$output_file" in
  /*) ;;
  *) output_file="$repository_root/$output_file" ;;
esac
output_directory=$(dirname -- "$output_file")
if [[ ! -d "$output_directory" ]]; then
  install -d -m 0750 "$output_directory"
fi
temporary_output=$(mktemp "$output_file.XXXXXX")
cat >"$temporary_output" <<EOF
DRIVEMPVD_RELEASE_REFERENCE=$reference
DRIVEMPVD_RELEASE_COMMIT=$commit
DRIVEMPVD_RELEASE_ARCHIVE_SHA256=$archive_sha256
DRIVEMPVD_RELEASE_PREPARED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
chmod 0644 "$temporary_output"
mv -f "$temporary_output" "$output_file"
temporary_output=""
printf 'Prepared release manifest: %s\n' "$output_file"
