#!/usr/bin/env python3
"""Fail-fast production preflight without printing deployment secrets."""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import unquote, urlparse

_REQUIRED_VALUES = {
    "DRIVEMPVD_ENVIRONMENT": "production",
    "DRIVEMPVD_DOCS_ENABLED": "false",
    "DRIVEMPVD_AUTH_COOKIE_SECURE": "true",
    "DRIVEMPVD_TLS_ENABLED": "true",
}
_SECRET_KEYS = (
    "POSTGRES_PASSWORD",
    "DRIVEMPVD_JWT_ACCESS_SECRET",
    "DRIVEMPVD_JWT_REFRESH_SECRET",
    "DRIVEMPVD_AUTH_SECRET_PEPPER",
)
_PLACEHOLDER_MARKERS = ("change-me", "development-", "replace-", "example.com")
_FLOATING_IMAGE_TAGS = {
    "local",
    "latest",
    "dev",
    "development",
    "edge",
    "main",
    "master",
    "nightly",
    "stable",
}
_SIZE_PATTERN = re.compile(r"(?P<amount>\d+)(?P<unit>[kmg])?", re.IGNORECASE)
_MEBIBYTE = 1024 * 1024
_GIBIBYTE = 1024 * _MEBIBYTE


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path("docker/.env"),
        help="Compose environment file to audit (default: docker/.env).",
    )
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip `docker compose config --quiet`; only for offline review.",
    )
    return parser.parse_args()


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse simple Compose .env entries without evaluating shell syntax."""
    values: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key or not key.replace("_", "").isalnum():
            msg = f"invalid .env entry at line {line_number}"
            raise ValueError(msg)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def parse_size(value: str) -> int | None:
    """Parse the byte units accepted by Nginx client_max_body_size."""
    match = _SIZE_PATTERN.fullmatch(value.strip())
    if match is None:
        return None
    multipliers = {None: 1, "k": 1024, "m": _MEBIBYTE, "g": _GIBIBYTE}
    unit = match.group("unit")
    return int(match.group("amount")) * multipliers[unit.casefold() if unit else None]


def _is_placeholder(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def validate(
    values: Mapping[str, str],
    *,
    check_filesystem: bool,
) -> list[str]:
    """Return human-readable findings without exposing secret values."""
    findings: list[str] = []
    for key, expected in _REQUIRED_VALUES.items():
        if values.get(key, "").casefold() != expected:
            findings.append(f"{key} must be {expected!r} in production")

    secrets = [values.get(key, "") for key in _SECRET_KEYS]
    for key, value in zip(_SECRET_KEYS, secrets, strict=True):
        if len(value) < 32 or _is_placeholder(value):
            findings.append(
                f"{key} must be a non-placeholder secret of at least 32 bytes"
            )
    if len(set(secrets)) != len(secrets):
        findings.append(
            "authentication secrets and PostgreSQL password must be distinct"
        )

    image_tag = values.get("DRIVEMPVD_IMAGE_TAG", "")
    if (
        not image_tag
        or _is_placeholder(image_tag)
        or image_tag.casefold() in _FLOATING_IMAGE_TAGS
    ):
        findings.append(
            "DRIVEMPVD_IMAGE_TAG must identify a specific, non-floating "
            "production release"
        )

    database_url = values.get("DRIVEMPVD_DATABASE_URL", "")
    if not database_url or _is_placeholder(database_url):
        findings.append(
            "DRIVEMPVD_DATABASE_URL must not contain an example placeholder"
        )
    else:
        _validate_database_url(values, database_url, findings)

    for key in ("POSTGRES_DB", "POSTGRES_USER"):
        value = values.get(key, "")
        if not value or _is_placeholder(value):
            findings.append(f"{key} must not be empty or an example placeholder")

    if values.get("DRIVEMPVD_STORAGE_ROOT") != "/data/storage":
        findings.append(
            "DRIVEMPVD_STORAGE_ROOT must remain /data/storage inside the API container"
        )

    if values.get("VITE_API_BASE_URL") != "/api/v1":
        findings.append("VITE_API_BASE_URL must remain /api/v1 in production")

    maximum_upload = values.get("DRIVEMPVD_MAX_UPLOAD_SIZE_BYTES", "")
    try:
        maximum_upload_bytes = int(maximum_upload)
    except ValueError:
        findings.append("DRIVEMPVD_MAX_UPLOAD_SIZE_BYTES must be a positive integer")
        maximum_upload_bytes = 0
    if maximum_upload_bytes <= 0:
        findings.append("DRIVEMPVD_MAX_UPLOAD_SIZE_BYTES must be positive")

    nginx_limit = parse_size(values.get("DRIVEMPVD_NGINX_CLIENT_MAX_BODY_SIZE", ""))
    if nginx_limit is None or nginx_limit < maximum_upload_bytes:
        findings.append(
            "DRIVEMPVD_NGINX_CLIENT_MAX_BODY_SIZE must be at least "
            "DRIVEMPVD_MAX_UPLOAD_SIZE_BYTES"
        )

    storage_path_value = values.get("DRIVEMPVD_STORAGE_PATH", "")
    if not storage_path_value.startswith("/"):
        findings.append("DRIVEMPVD_STORAGE_PATH must be an absolute host path")
    elif check_filesystem:
        _validate_storage_path(Path(storage_path_value), findings)

    certificate_path_value = values.get("DRIVEMPVD_TLS_CERTIFICATES_PATH", "")
    if certificate_path_value.startswith("/etc/letsencrypt/live/"):
        findings.append(
            "DRIVEMPVD_TLS_CERTIFICATES_PATH must contain dereferenced PEM "
            "files, not Certbot's live/ symlinks"
        )
    elif not certificate_path_value.startswith("/"):
        findings.append("DRIVEMPVD_TLS_CERTIFICATES_PATH must be an absolute host path")
    elif check_filesystem:
        _validate_certificates(Path(certificate_path_value), findings)

    acme_path_value = values.get("DRIVEMPVD_ACME_WEBROOT_PATH", "")
    if not acme_path_value.startswith("/"):
        findings.append("DRIVEMPVD_ACME_WEBROOT_PATH must be an absolute host path")
    elif check_filesystem and not Path(acme_path_value).is_dir():
        findings.append("DRIVEMPVD_ACME_WEBROOT_PATH does not exist as a directory")

    ports: dict[str, int] = {}
    for key in ("DRIVEMPVD_HTTP_PORT", "DRIVEMPVD_HTTPS_PORT"):
        try:
            port = int(values.get(key, ""))
        except ValueError:
            port = 0
        if not 1 <= port <= 65535:
            findings.append(f"{key} must be a valid TCP port")
        ports[key] = port
    if (
        all(1 <= port <= 65535 for port in ports.values())
        and ports["DRIVEMPVD_HTTP_PORT"] == ports["DRIVEMPVD_HTTPS_PORT"]
    ):
        findings.append("DRIVEMPVD_HTTP_PORT and DRIVEMPVD_HTTPS_PORT must differ")
    return findings


def _validate_storage_path(path: Path, findings: list[str]) -> None:
    if not path.is_dir():
        findings.append("DRIVEMPVD_STORAGE_PATH does not exist as a directory")
        return
    if os.name != "posix":
        return
    metadata = path.stat()
    if (metadata.st_uid, metadata.st_gid) != (10001, 10001):
        findings.append("DRIVEMPVD_STORAGE_PATH must be owned by UID:GID 10001:10001")
    if not metadata.st_mode & stat.S_IWUSR:
        findings.append("DRIVEMPVD_STORAGE_PATH owner must have write permission")


def _validate_database_url(
    values: Mapping[str, str],
    database_url: str,
    findings: list[str],
) -> None:
    parsed = urlparse(database_url)
    expected_user = values.get("POSTGRES_USER")
    expected_password = values.get("POSTGRES_PASSWORD")
    expected_database = values.get("POSTGRES_DB")
    if parsed.scheme != "postgresql+asyncpg" or parsed.hostname != "postgres":
        findings.append(
            "DRIVEMPVD_DATABASE_URL must target the internal postgres service"
        )
    if not expected_user or parsed.username != expected_user:
        findings.append("DRIVEMPVD_DATABASE_URL user must match POSTGRES_USER")
    if not expected_password or unquote(parsed.password or "") != expected_password:
        findings.append("DRIVEMPVD_DATABASE_URL password must match POSTGRES_PASSWORD")
    database_name = parsed.path.removeprefix("/")
    if not expected_database or database_name != expected_database:
        findings.append("DRIVEMPVD_DATABASE_URL database must match POSTGRES_DB")


def _validate_certificates(path: Path, findings: list[str]) -> None:
    for name in ("fullchain.pem", "privkey.pem"):
        candidate = path / name
        if not candidate.is_file():
            findings.append(f"TLS certificate file is missing: {name}")
        elif candidate.is_symlink():
            findings.append(f"TLS certificate file must be dereferenced: {name}")
        elif name == "privkey.pem" and os.name == "posix":
            mode = stat.S_IMODE(candidate.stat().st_mode)
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                findings.append("TLS private key must not grant group or other access")


def _validate_compose(environment_file: Path) -> str | None:
    command = [
        "docker",
        "compose",
        "--env-file",
        str(environment_file),
        "-f",
        "compose.yaml",
        "config",
        "--quiet",
    ]
    try:
        subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return "Docker Engine and the Docker Compose v2 plugin are required"
    except subprocess.CalledProcessError:
        return "docker compose config --quiet failed; inspect the deployment host logs"
    return None


def main() -> None:
    arguments = _arguments()
    environment_file = arguments.env_file.resolve()
    if not environment_file.is_file():
        message = f"preflight error: environment file is missing: {environment_file}"
        raise SystemExit(message)
    try:
        values = parse_env_file(environment_file)
    except ValueError as exc:
        raise SystemExit(f"preflight error: {exc}") from exc
    findings = validate(values, check_filesystem=not arguments.skip_docker)
    if not arguments.skip_docker:
        compose_finding = _validate_compose(environment_file)
        if compose_finding is not None:
            findings.append(compose_finding)
    if findings:
        print("Production preflight failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        raise SystemExit(1)
    print("Production preflight passed.")


if __name__ == "__main__":
    main()
