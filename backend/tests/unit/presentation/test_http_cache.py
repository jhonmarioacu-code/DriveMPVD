from datetime import UTC, datetime

from fastapi import Request, Response

from app.presentation.http_cache import (
    apply_cache_headers,
    conditional_not_modified,
    metadata_etag,
)


def _request(**headers: str) -> Request:
    encoded = [
        (name.lower().encode(), value.encode()) for name, value in headers.items()
    ]
    return Request({"type": "http", "headers": encoded})


def test_metadata_etag_is_stable_and_cache_headers_support_naive_dates() -> None:
    assert metadata_etag(("a", "b")) == metadata_etag(("a", "b"))
    assert metadata_etag(("a", "b")) != metadata_etag(("b", "a"))
    response = Response()

    apply_cache_headers(
        response,
        etag='"etag"',
        last_modified=datetime(2026, 7, 18, 12, 0, tzinfo=UTC).replace(tzinfo=None),
    )

    assert response.headers["etag"] == '"etag"'
    assert response.headers["last-modified"].endswith("GMT")


def test_if_none_match_takes_precedence_and_supports_wildcard() -> None:
    modified = datetime(2026, 7, 18, tzinfo=UTC)

    cached = conditional_not_modified(
        _request(**{"if-none-match": "*"}),
        etag='"etag"',
        last_modified=modified,
    )
    assert cached is not None
    assert cached.status_code == 304
    assert (
        conditional_not_modified(
            _request(
                **{
                    "if-none-match": '"different"',
                    "if-modified-since": "Sat, 18 Jul 2037 00:00:00 GMT",
                }
            ),
            etag='"etag"',
            last_modified=modified,
        )
        is None
    )


def test_invalid_or_older_if_modified_since_requires_representation() -> None:
    modified = datetime(2026, 7, 18, tzinfo=UTC)

    assert (
        conditional_not_modified(
            _request(**{"if-modified-since": "invalid"}),
            etag='"etag"',
            last_modified=modified,
        )
        is None
    )
    assert (
        conditional_not_modified(
            _request(**{"if-modified-since": "Sat, 18 Jul 2020 00:00:00 GMT"}),
            etag='"etag"',
            last_modified=modified,
        )
        is None
    )
    assert (
        conditional_not_modified(
            _request(),
            etag='"etag"',
            last_modified=None,
        )
        is None
    )
