import getpass
import io
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.application.dtos.auth import ChangeAdminPasswordCommandDTO
from app.infrastructure.cli import change_admin_password
from app.infrastructure.container import ApplicationContainer


@dataclass
class FakeDatabase:
    disposed: bool = False

    async def dispose(self) -> None:
        self.disposed = True


class FakeChangePassword:
    def __init__(self) -> None:
        self.command: ChangeAdminPasswordCommandDTO | None = None

    async def execute(self, command: ChangeAdminPasswordCommandDTO) -> Any:
        self.command = command
        return SimpleNamespace(username=command.username, id=uuid4())


@dataclass
class FakeContainer:
    change_admin_password: FakeChangePassword
    database: FakeDatabase


async def test_change_disposes_database_and_reports_account(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    container = FakeContainer(FakeChangePassword(), FakeDatabase())
    monkeypatch.setattr(change_admin_password, "load_settings", lambda: object())
    monkeypatch.setattr(ApplicationContainer, "build", lambda settings: container)

    await change_admin_password._change("Admin", "correct horse battery staple")

    assert container.change_admin_password.command is not None
    assert container.database.disposed
    assert "Administrator password changed: Admin" in capsys.readouterr().out


def test_main_reads_matching_passwords_without_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(("correct horse battery staple", "correct horse battery staple"))
    received: list[tuple[str, str]] = []

    async def fake_change(username: str, password: str) -> None:
        received.append((username, password))

    monkeypatch.setattr(sys, "argv", ["change_admin_password", "Admin"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt: next(answers))
    monkeypatch.setattr(change_admin_password, "_change", fake_change)

    change_admin_password.main()

    assert received == [("Admin", "correct horse battery staple")]


def test_main_rejects_password_confirmation_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(("first secure password", "different secure password"))
    monkeypatch.setattr(sys, "argv", ["change_admin_password", "Admin"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt: next(answers))

    with pytest.raises(SystemExit):
        change_admin_password.main()


def test_main_accepts_explicit_password_stdin_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[tuple[str, str]] = []

    async def fake_change(username: str, password: str) -> None:
        received.append((username, password))

    monkeypatch.setattr(
        sys,
        "argv",
        ["change_admin_password", "--password-stdin", "Admin"],
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("stdin secure password\n"))
    monkeypatch.setattr(change_admin_password, "_change", fake_change)

    change_admin_password.main()

    assert received == [("Admin", "stdin secure password")]
