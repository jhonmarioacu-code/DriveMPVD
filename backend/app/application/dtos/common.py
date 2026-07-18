"""DTOs shared by application use cases."""

from dataclasses import dataclass

from app.application.exceptions import ApplicationValidationError


@dataclass(frozen=True, slots=True)
class PageDTO[ItemT]:
    """A bounded page returned by a query use case."""

    items: tuple[ItemT, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class PageRequestDTO:
    """Validated bounds shared by paginated application queries."""

    limit: int

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 200:
            raise ApplicationValidationError("Page limit must be between 1 and 200.")
