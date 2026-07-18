"""DTOs shared by application use cases."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageDTO[ItemT]:
    """A bounded page returned by a query use case."""

    items: tuple[ItemT, ...]
    next_cursor: str | None
