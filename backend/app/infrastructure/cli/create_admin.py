"""Secure interactive bootstrap command for the singleton administrator."""

import argparse
import asyncio
import getpass
import sys

from app.application.dtos.auth import BootstrapAdminCommandDTO
from app.infrastructure.config import load_settings
from app.infrastructure.container import ApplicationContainer


async def _create(username: str, password: str) -> None:
    container = ApplicationContainer.build(load_settings())
    try:
        account = await container.bootstrap_admin.execute(
            BootstrapAdminCommandDTO(username=username, password=password)
        )
    finally:
        await container.database.dispose()
    print(f"Administrator created: {account.username} ({account.id})")


def main() -> None:
    """Prompt without exposing the password in process arguments or shell history."""
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
        password = getpass.getpass("Administrator password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            parser.error("passwords do not match")
    asyncio.run(_create(args.username, password))


if __name__ == "__main__":
    main()
