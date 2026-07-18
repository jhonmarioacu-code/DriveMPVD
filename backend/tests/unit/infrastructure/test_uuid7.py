import pytest

from app.infrastructure.persistence.identifiers import Uuid7Generator


def test_uuid7_has_rfc_version_variant_and_embedded_timestamp() -> None:
    generator = Uuid7Generator(
        clock_ms=lambda: 1_700_000_000_123,
        random_bits=lambda _: 42,
    )

    identifier = generator.new()

    assert identifier.version == 7
    assert identifier.variant == "specified in RFC 4122"
    assert identifier.int >> 80 == 1_700_000_000_123


def test_uuid7_is_monotonic_when_clock_stalls_or_moves_backwards() -> None:
    timestamps = iter([1000, 1000, 999])
    generator = Uuid7Generator(
        clock_ms=lambda: next(timestamps),
        random_bits=lambda _: 10,
    )

    identifiers = [generator.new(), generator.new(), generator.new()]

    assert identifiers == sorted(identifiers)
    assert len(set(identifiers)) == 3


def test_uuid7_advances_timestamp_if_random_sequence_wraps() -> None:
    maximum_random = (1 << 74) - 1
    generator = Uuid7Generator(
        clock_ms=lambda: 1000,
        random_bits=lambda _: maximum_random,
    )

    first = generator.new()
    second = generator.new()

    assert first.int >> 80 == 1000
    assert second.int >> 80 == 1001


def test_uuid7_rejects_timestamp_overflow() -> None:
    generator = Uuid7Generator(clock_ms=lambda: 1 << 48)

    with pytest.raises(OverflowError, match="48-bit"):
        generator.new()
