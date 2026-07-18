"""RFC 9562 UUID version 7 generation without infrastructure dependencies."""

import secrets
import time
from collections.abc import Callable
from threading import Lock
from typing import Final
from uuid import UUID

_RANDOM_BITS: Final[int] = 74
_RANDOM_MASK: Final[int] = (1 << _RANDOM_BITS) - 1
_TIMESTAMP_MASK: Final[int] = (1 << 48) - 1


class Uuid7Generator:
    """Generate thread-safe, monotonically ordered UUID version 7 values."""

    def __init__(
        self,
        *,
        clock_ms: Callable[[], int] | None = None,
        random_bits: Callable[[int], int] | None = None,
    ) -> None:
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._random_bits = random_bits or secrets.randbits
        self._lock = Lock()
        self._last_timestamp = -1
        self._last_random = -1

    def new(self) -> UUID:
        """Return a UUID7, preserving order within one process and millisecond."""
        with self._lock:
            timestamp = max(self._clock_ms(), self._last_timestamp)
            if timestamp > _TIMESTAMP_MASK:
                msg = "UUID7 timestamp exceeds its 48-bit representation"
                raise OverflowError(msg)

            if timestamp == self._last_timestamp:
                random_value = (self._last_random + 1) & _RANDOM_MASK
                if random_value == 0:
                    timestamp += 1
                    random_value = self._random_bits(_RANDOM_BITS)
            else:
                random_value = self._random_bits(_RANDOM_BITS)

            self._last_timestamp = timestamp
            self._last_random = random_value

            random_a = random_value >> 62
            random_b = random_value & ((1 << 62) - 1)
            value = (
                (timestamp << 80)
                | (0x7 << 76)
                | (random_a << 64)
                | (0b10 << 62)
                | random_b
            )
            return UUID(int=value)
