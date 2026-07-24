import getpass
import io
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.application.dtos.auth import BootstrapAdminCommandDTO
from app.infrastructure.cli import create_admin
from app.infrastructure.container import ApplicationContainer


@dataclass
class FakeDatabase:
    disposed: bool = False

    async def dispose(self) -> None:
        self.disposed = True


class FakeBootstrap:
    def __init__(self) -> None:
        self.command: BootstrapAdminCommandDTO | None = None

    async def execute(self, command: BootstrapAdminCommandDTO) -> Any:
        self.command = command
        return SimpleNamespace(username=command.username, id=uuid4())


@dataclass
class FakeContainer:
    bootstrap_admin: FakeBootstrap
    database: FakeDatabase


async def test_create_disposes_database_and_reports_account(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    container = FakeContainer(FakeBootstrap(), FakeDatabase())
    monkeypatch.setattr(create_admin, "load_settings", lambda: object())
    monkeypatch.setattr(
        ApplicationContainer,
        "build",
        lambda settings: container,
    )

    await create_admin._create("Admin", "correct horse battery staple")

    assert container.bootstrap_admin.command is not None
    assert container.database.disposed
    assert "Administrator created: Admin" in capsys.readouterr().out


def test_main_reads_matching_passwords_without_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(("correct horse battery staple", "correct horse battery staple"))
    received: list[tuple[str, str]] = []

    async def fake_create(username: str, password: str) -> None:
        received.append((username, password))

    monkeypatch.setattr(sys, "argv", ["create_admin", "Admin"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt: next(answers))
    monkeypatch.setattr(create_admin, "_create", fake_create)

    create_admin.main()

    assert received == [("Admin", "correct horse battery staple")]


def test_main_rejects_password_confirmation_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(("first secure password", "different secure password"))
    monkeypatch.setattr(sys, "argv", ["create_admin", "Admin"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt: next(answers))

    with pytest.raises(SystemExit):
        create_admin.main()


def test_main_accepts_explicit_password_stdin_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[tuple[str, str]] = []

    async def fake_create(username: str, password: str) -> None:
        received.append((username, password))

    monkeypatch.setattr(
        sys,
        "argv",
        ["create_admin", "--password-stdin", "Admin"],
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("stdin secure password\n"))
    monkeypatch.setattr(create_admin, "_create", fake_create)

    create_admin.main()

    assert received == [("Admin", "stdin secure password")]
