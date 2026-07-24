"""Unit coverage for safe credentials in the deployment benchmark client."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


def _load_benchmark_module() -> Any:
    backend_root = Path(__file__).resolve().parents[2]
    path = backend_root / "scripts" / "benchmark_deployment.py"
    specification = importlib.util.spec_from_file_location("deployment_benchmark", path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def test_benchmark_reads_a_password_from_a_protected_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    benchmark = _load_benchmark_module()
    password_file = tmp_path / "benchmark-password"
    password_file.write_text("secret value\n", encoding="utf-8")
    monkeypatch.delenv("DRIVEMPVD_BENCHMARK_PASSWORD", raising=False)
    monkeypatch.setenv("DRIVEMPVD_BENCHMARK_PASSWORD_FILE", str(password_file))

    assert benchmark._password_from_environment() == "secret value"


def test_benchmark_rejects_an_unreadable_password_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    benchmark = _load_benchmark_module()
    monkeypatch.setenv(
        "DRIVEMPVD_BENCHMARK_PASSWORD_FILE",
        "C:/missing/benchmark-password",
    )

    with pytest.raises(ValueError, match="PASSWORD_FILE"):
        benchmark._password_from_environment()


def test_storage_benchmark_bootstraps_the_backend_import_path(tmp_path: Path) -> None:
    backend_root = Path(__file__).resolve().parents[2]
    script = backend_root / "scripts" / "benchmark_storage.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        check=False,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Benchmark local resumable upload" in completed.stdout
