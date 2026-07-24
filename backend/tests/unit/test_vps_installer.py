"""Static safety contract for the fresh-VPS installer."""

from pathlib import Path


def test_installer_covers_host_provisioning_and_runtime_validation() -> None:
    project_root = Path(__file__).resolve().parents[3]
    installer = (project_root / "docker" / "install-vps.sh").read_text(encoding="utf-8")

    assert 'VERSION_ID:-}" == "24.04"' in installer
    assert "apt-get upgrade -y" in installer
    assert "docker-buildx docker-compose-v2 docker.io" in installer
    assert "python3 rsync ufw unattended-upgrades" in installer
    assert "ufw default deny incoming" in installer
    assert 'http_port="127.0.0.1:8080"' in installer
    assert "docker/preflight.py" in installer
    assert "certbot reconfigure" in installer
    assert "docker/verify-deployment.sh" in installer
    assert "build postgres api frontend nginx" in installer
    assert "up --no-build --wait -d" in installer
    assert "--smoke-password-file" in installer
    assert 'chmod -R go-w -- "$repository_root"' in installer
    assert 'environment_dir="/etc/drivempvd"' in installer
    assert 'environment_file="$environment_dir/${mode}.env"' in installer
    assert "DRIVEMPVD_COMPOSE_ENV_FILE=$environment_file" in installer
    assert (
        "production installation requires --repository and an immutable --release"
        in installer
    )
    assert 'rev-parse --verify "${release_ref}^{commit}"' in installer
    assert "DRIVEMPVD_RELEASE_COMMIT=$release_commit" in installer
    assert 'mv -- "$legacy_environment_file" "$legacy_backup"' in installer
    assert "DRIVEMPVD_OUTBOX_WORKER_POLL_SECONDS=5" in installer
    assert "DRIVEMPVD_OUTBOX_ORPHAN_SWEEP_BATCH_SIZE=100" in installer
    assert "DRIVEMPVD_WORKER_MEMORY_LIMIT=$worker_memory_limit" in installer
    assert "down --volumes" not in installer
    assert "printf '%s\\n' \"$admin_password\"" in installer
    assert "--password-stdin" in installer


def test_certbot_hook_dereferences_keys_and_reloads_nginx() -> None:
    project_root = Path(__file__).resolve().parents[3]
    hook = (project_root / "docker" / "certbot-deploy-hook.sh").read_text(
        encoding="utf-8"
    )

    assert "RENEWED_LINEAGE" in hook
    assert 'readlink -f "$RENEWED_LINEAGE/privkey.pem"' in hook
    assert "exec -T nginx nginx -c /tmp/drivempvd-nginx/nginx.conf -s reload" in hook
    assert "install -m 0640 -o root -g 101" in hook


def test_host_test_script_uses_an_isolated_disposable_database() -> None:
    project_root = Path(__file__).resolve().parents[3]
    verifier = (project_root / "docker" / "verify-postgresql-tests.sh").read_text(
        encoding="utf-8"
    )

    assert "docker/postgres.Dockerfile" in verifier
    assert '"$database_image"' in verifier
    assert "docker/backend.test.Dockerfile" in verifier
    assert "DRIVEMPVD_TEST_DATABASE_URL" in verifier
    assert "--tmpfs /var/lib/postgresql/data" in verifier
    assert "--read-only" in verifier
    assert "--cap-drop ALL" in verifier
    assert "python -m ruff check app tests" in verifier
    assert "python -m mypy app tests" in verifier
    assert "python -m pytest" in verifier
    assert "python -m pip_audit -r requirements.lock" in verifier
    assert "--env XDG_CACHE_HOME=/tmp" in verifier
    assert "drivempvd_postgres_data" not in verifier


def test_backup_restore_drill_never_restores_into_product_storage() -> None:
    project_root = Path(__file__).resolve().parents[3]
    drill = (project_root / "docker" / "verify-backup-restore.sh").read_text(
        encoding="utf-8"
    )

    assert "restore-drill.XXXXXX" in drill
    assert "drivempvd-restore-drill-$$" in drill
    assert "--tmpfs /var/lib/postgresql/data" in drill
    assert "DRIVEMPVD_RESTORE_IMAGE" in drill
    assert 'rm -rf -- "$restore_root"' in drill
    assert "pg_restore --exit-on-error --no-owner --no-acl" in drill
    assert "write_services=(nginx api worker)" in drill
    assert 'stop "${write_services[@]}"' in drill
    assert 'up -d --wait "${write_services[@]}"' in drill
    assert "DRIVEMPVD_COMPOSE_ENV_FILE" in drill
    assert "DRIVEMPVD_STORAGE_PATH" in drill
    assert "flock -n 9" in drill
    assert (
        '--mount "type=bind,src=$backup_root/database.dump,'
        'dst=/tmp/database.dump,readonly"' in drill
    )
    assert "docker cp" not in drill
    assert 'docker exec -u 0 "$restore_container" pg_restore' in drill


def test_password_rotation_keeps_the_secret_out_of_arguments_and_logs() -> None:
    project_root = Path(__file__).resolve().parents[3]
    rotation = (project_root / "docker" / "rotate-admin-password.sh").read_text(
        encoding="utf-8"
    )

    assert "openssl rand -hex 24" in rotation
    assert "change_admin_password" in rotation
    assert "printf '%s\\n' \"$password\"" in rotation
    assert "--password-stdin" in rotation
    assert "DRIVEMPVD_SMOKE_PASSWORD_FILE" in rotation
    assert 'DRIVEMPVD_COMPOSE_ENV_FILE="$environment_file"' in rotation
    assert "DRIVEMPVD_SMOKE_BASE_URL=http://127.0.0.1:8080" not in rotation
    assert 'echo "$password"' not in rotation


def test_deployment_smoke_requires_a_healthy_storage_worker() -> None:
    project_root = Path(__file__).resolve().parents[3]
    smoke = (project_root / "docker" / "verify-deployment.sh").read_text(
        encoding="utf-8"
    )

    assert "verify_worker_health" in smoke
    assert "Storage outbox worker is not healthy" in smoke
    assert "ps -q worker" in smoke


def test_container_scan_is_pinned_and_fails_on_fixed_severe_findings() -> None:
    project_root = Path(__file__).resolve().parents[3]
    scan = (project_root / "docker" / "verify-container-images.sh").read_text(
        encoding="utf-8"
    )
    source_scan = (project_root / "docker" / "verify-source-security.sh").read_text(
        encoding="utf-8"
    )

    assert "aquasec/trivy:latest@sha256:" in scan
    assert "DRIVEMPVD_IMAGE_TAG:-" in scan
    assert "DRIVEMPVD_COMPOSE_ENV_FILE" in scan
    assert "--severity HIGH,CRITICAL" in scan
    assert "--ignore-unfixed" in scan
    assert "total=$((total + findings))" in scan
    assert "((total == 0))" in scan
    assert "secret,misconfig" in source_scan
    assert "--severity HIGH,CRITICAL" in source_scan
    assert "--exclude='./docker/.env'" in source_scan


def test_zap_baseline_is_pinned_and_requires_an_explicit_target() -> None:
    project_root = Path(__file__).resolve().parents[3]
    scanner = (project_root / "docker" / "verify-zap-baseline.sh").read_text(
        encoding="utf-8"
    )

    assert "ghcr.io/zaproxy/zaproxy:stable@sha256:" in scanner
    assert "DRIVEMPVD_ZAP_TARGET" in scanner
    assert '[[ "$target" =~ ^https?:// ]]' in scanner
    assert "--memory=1g" in scanner
    assert "--pids-limit=256" in scanner
    assert "zap-baseline.py" in scanner
    assert "-I" in scanner


def test_storage_benchmark_runs_in_an_isolated_unprivileged_container() -> None:
    project_root = Path(__file__).resolve().parents[3]
    benchmark = (project_root / "docker" / "benchmark-storage.sh").read_text(
        encoding="utf-8"
    )

    assert "DRIVEMPVD_STORAGE_BENCHMARK_DIR" in benchmark
    assert '"$benchmark_dir" = /*' in benchmark
    assert "backend.test.Dockerfile" in benchmark
    assert "--read-only" in benchmark
    assert "--cap-drop ALL" in benchmark
    assert '--mount "type=bind,src=$benchmark_dir' in benchmark
    assert "python scripts/benchmark_storage.py" in benchmark


def test_ci_workflow_runs_the_reproducible_quality_gates() -> None:
    project_root = Path(__file__).resolve().parents[3]
    workflow = (project_root / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683" in workflow
    assert "docker/verify-source-security.sh" in workflow
    assert "docker/verify-postgresql-tests.sh" in workflow
    assert "docker/verify-frontend.sh" in workflow
    assert "Deployment contracts" in workflow
    assert "bash -n" in workflow
    assert "docker compose --env-file docker/.env.example" in workflow


def test_release_and_transport_scripts_keep_provenance_and_ssh_safety() -> None:
    project_root = Path(__file__).resolve().parents[3]
    scripts_root = project_root / "scripts"
    prepare = (scripts_root / "release" / "prepare-release.sh").read_text(
        encoding="utf-8"
    )
    rsync_transfer = (scripts_root / "transfer" / "push-rsync.sh").read_text(
        encoding="utf-8"
    )
    scp_transfer = (scripts_root / "transfer" / "push-scp.sh").read_text(
        encoding="utf-8"
    )
    sftp_transfer = (scripts_root / "transfer" / "push-sftp.sh").read_text(
        encoding="utf-8"
    )
    ftp = (scripts_root / "transfer" / "ftp-not-supported.sh").read_text(
        encoding="utf-8"
    )
    powershell = (scripts_root / "Deploy-DriveMPVD.ps1").read_text(encoding="utf-8")

    assert "status --porcelain --untracked-files=all" in prepare
    assert 'rev-parse --verify "$reference^{commit}"' in prepare
    assert "DRIVEMPVD_RELEASE_ARCHIVE_SHA256" in prepare
    assert "drivempvd-release-manifests" in prepare
    assert "release-$commit.env" in prepare
    for transfer in (rsync_transfer, scp_transfer, sftp_transfer):
        assert "StrictHostKeyChecking=yes" in transfer
        assert "test ! -e '$final'" in transfer
        assert "/srv/drivempvd/releases" in transfer
    assert "FTP is not supported" in ftp
    assert "exit 64" in ftp
    assert "StrictHostKeyChecking=yes" in powershell
    assert "Checkout HEAD must equal -Release" in powershell
