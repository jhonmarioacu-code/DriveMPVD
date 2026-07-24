"""Regression coverage for importing the ASGI entrypoint in a clean process."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_asgi_entrypoint_imports_in_a_clean_python_process() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    environment = os.environ | {
        "DRIVEMPVD_ENVIRONMENT": "test",
        "DRIVEMPVD_STORAGE_ROOT": str(Path.cwd().anchor),
    }

    result = subprocess.run(
        [sys.executable, "-c", "import app.main; assert app.main.app.title"],
        cwd=backend_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_application_module_exports_the_asgi_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DRIVEMPVD_STORAGE_ROOT", str(Path.cwd().anchor))
    from app.main import app

    assert app.title == "DriveMPVD"
