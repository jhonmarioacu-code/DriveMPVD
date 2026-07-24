"""Secure interactive password rotation for the singleton administrator."""

import argparse
import asyncio
import getpass
import sys

from app.application.dtos.auth import ChangeAdminPasswordCommandDTO
from app.infrastructure.config import load_settings
from app.infrastructure.container import ApplicationContainer


async def _change(username: str, password: str) -> None:
    container = ApplicationContainer.build(load_settings())
    try:
        account = await container.change_admin_password.execute(
            ChangeAdminPasswordCommandDTO(username=username, password=password)
        )
    finally:
        await container.database.dispose()
    print(f"Administrator password changed: {account.username} ({account.id})")


def main() -> None:
    """Read the new password without exposing it in arguments or shell history."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username", help="Administrator login name")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
        if not password:
            parser.error("password from stdin is empty")
    else:
        password = getpass.getpass("New administrator password: ")
        confirmation = getpass.getpass("Confirm new password: ")
        if password != confirmation:
            parser.error("passwords do not match")
    asyncio.run(_change(args.username, password))


if __name__ == "__main__":
    main()
