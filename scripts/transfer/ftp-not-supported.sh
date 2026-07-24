#!/usr/bin/env bash
# FTP intentionally fails closed: it is not a secure deployment transport.
set -Eeuo pipefail

printf '%s\n' \
  'FTP is not supported for DriveMPVD deployment.' \
  'It does not provide the required transport encryption or host verification.' \
  'Use Git, rsync over SSH, SCP, or SFTP with a verified host key instead.' >&2
exit 64
