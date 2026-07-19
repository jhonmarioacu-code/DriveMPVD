"""Tests for the secret-safe production deployment preflight."""

import importlib.util
from pathlib import Path
from typing import Any


def _load_preflight_module() -> Any:
    project_root = Path(__file__).resolve().parents[3]
    path = project_root / "docker" / "preflight.py"
    specification = importlib.util.spec_from_file_location("deployment_preflight", path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _valid_values() -> dict[str, str]:
    postgres_password = "p" * 40
    return {
        "DRIVEMPVD_ENVIRONMENT": "production",
        "DRIVEMPVD_DOCS_ENABLED": "false",
        "DRIVEMPVD_AUTH_COOKIE_SECURE": "true",
        "DRIVEMPVD_TLS_ENABLED": "true",
        "POSTGRES_PASSWORD": postgres_password,
        "DRIVEMPVD_JWT_ACCESS_SECRET": "a" * 40,
        "DRIVEMPVD_JWT_REFRESH_SECRET": "b" * 40,
        "DRIVEMPVD_AUTH_SECRET_PEPPER": "c" * 40,
        "DRIVEMPVD_IMAGE_TAG": "2026.07.19",
        "POSTGRES_DB": "drivempvd",
        "POSTGRES_USER": "drivempvd",
        "DRIVEMPVD_DATABASE_URL": (
            "postgresql+asyncpg://drivempvd:"
            f"{postgres_password}@postgres:5432/drivempvd"
        ),
        "DRIVEMPVD_STORAGE_ROOT": "/data/storage",
        "DRIVEMPVD_MAX_UPLOAD_SIZE_BYTES": str(50 * 1024 * 1024 * 1024),
        "DRIVEMPVD_NGINX_CLIENT_MAX_BODY_SIZE": "50g",
        "DRIVEMPVD_STORAGE_PATH": "/data/storage",
        "DRIVEMPVD_TLS_CERTIFICATES_PATH": "/etc/drivempvd/tls",
        "DRIVEMPVD_ACME_WEBROOT_PATH": "/var/lib/drivempvd/acme-webroot",
        "DRIVEMPVD_HTTP_PORT": "80",
        "DRIVEMPVD_HTTPS_PORT": "443",
    }


def test_preflight_accepts_a_complete_production_configuration() -> None:
    preflight = _load_preflight_module()

    assert preflight.validate(_valid_values(), check_filesystem=False) == []


def test_preflight_rejects_insecure_or_incoherent_values() -> None:
    preflight = _load_preflight_module()
    values = _valid_values()
    values.update(
        {
            "DRIVEMPVD_AUTH_COOKIE_SECURE": "false",
            "DRIVEMPVD_IMAGE_TAG": "latest",
            "DRIVEMPVD_NGINX_CLIENT_MAX_BODY_SIZE": "1g",
            "DRIVEMPVD_TLS_CERTIFICATES_PATH": "/etc/letsencrypt/live/example.com",
            "DRIVEMPVD_HTTPS_PORT": "80",
        }
    )

    findings = preflight.validate(values, check_filesystem=False)

    assert any("AUTH_COOKIE_SECURE" in finding for finding in findings)
    assert any("non-floating" in finding for finding in findings)
    assert any("NGINX_CLIENT_MAX_BODY_SIZE" in finding for finding in findings)
    assert any("dereferenced PEM" in finding for finding in findings)
    assert any("must differ" in finding for finding in findings)


def test_deployment_files_keep_the_hardened_proxy_and_smoke_contract() -> None:
    project_root = Path(__file__).resolve().parents[3]
    compose = (project_root / "compose.yaml").read_text(encoding="utf-8")
    nginx = (project_root / "docker/nginx/nginx.conf.template").read_text(
        encoding="utf-8"
    )
    locations = (project_root / "docker/nginx/locations.conf").read_text(
        encoding="utf-8"
    )
    proxy_headers = (project_root / "docker/nginx/proxy-headers.conf").read_text(
        encoding="utf-8"
    )
    selector = (project_root / "docker/nginx/40-select-configuration.sh").read_text(
        encoding="utf-8"
    )
    smoke = (project_root / "docker/verify-deployment.sh").read_text(encoding="utf-8")

    assert "internal: true" in compose
    assert "DRIVEMPVD_IMAGE_TAG" in compose
    assert "resolver 127.0.0.11" in nginx
    assert '"request":"$request"' not in nginx
    assert "limit_conn uploads_per_ip 2;" in locations
    assert "proxy_request_buffering off;" in locations
    assert "return 404;" in locations
    assert "X-Forwarded-For $remote_addr" in proxy_headers
    assert "$proxy_add_x_forwarded_for" not in proxy_headers
    assert "production requires DRIVEMPVD_TLS_ENABLED=true" in selector
    assert "DRIVEMPVD_SMOKE_PASSWORD_FILE" in smoke
    assert "compose_env_value" in smoke
    assert "DRIVEMPVD_SMOKE_BASE_URL must be set" in smoke
    assert '"password": sys.argv[2]' not in smoke
    assert '--data "$login_payload"' not in smoke
    assert '--data-binary "@$login_payload"' in smoke
    assert "HttpOnly" in smoke
    assert "SameSite=Strict" in smoke
    assert "Path=/api/v1/auth" in smoke
    assert "csrf_status=" in smoke
    assert "purge_entry" in smoke
    assert "Range: bytes=0-3" in smoke
