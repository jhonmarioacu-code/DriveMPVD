"""Transaction boundary exposed to application use cases."""

from types import TracebackType
from typing import Protocol, Self

from app.application.ports.outbox_repository import OutboxRepository


class UnitOfWork(Protocol):
    """Own one atomic transaction and its repositories."""

    @property
    def outbox(self) -> OutboxRepository:
        """Return the outbox repository bound to this transaction."""
        ...

    async def __aenter__(self) -> Self:
        """Open a transaction."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Rollback unfinished or failed work and release resources."""
        ...

    async def commit(self) -> None:
        """Atomically commit every staged write."""
        ...

    async def rollback(self) -> None:
        """Discard every staged write."""
        ...


class UnitOfWorkFactory(Protocol):
    """Create a fresh Unit of Work for one use-case execution."""

    def __call__(self) -> UnitOfWork:
        """Return a non-started Unit of Work."""
        ...
