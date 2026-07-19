"""Authenticated end-to-end transfer benchmark for a running DriveMPVD stack.

Run this from the checkout on the Ubuntu host after Docker Compose and the
administrator account are available. The script streams a pre-existing file in
bounded chunks; it never reads the complete payload into Python memory.
"""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import os
import statistics
import sys
import time
import tracemalloc
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPCookieProcessor, OpenerDirector, Request, build_opener
from uuid import uuid4

_MEBIBYTE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class BenchmarkConfiguration:
    base_url: str
    api_prefix: str
    chunk_size: int
    download_block_size: int
    csrf_cookie_name: str
    keep_entry: bool
    source_path: Path
    username: str
    password: str


class BenchmarkRequestError(RuntimeError):
    """Represent a non-successful API response without exposing credentials."""


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark authenticated resumable upload, download and Range delivery."
        )
    )
    parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="Existing payload to transfer.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get(
            "DRIVEMPVD_BENCHMARK_BASE_URL",
            "http://127.0.0.1:8080",
        ),
        help=(
            "Public DriveMPVD URL (default: DRIVEMPVD_BENCHMARK_BASE_URL "
            "or localhost)."
        ),
    )
    parser.add_argument("--api-prefix", default="/api/v1")
    parser.add_argument(
        "--chunk-mib",
        type=int,
        default=4,
        help="Resumable upload chunk size in MiB, from 1 through 16 (default: 4).",
    )
    parser.add_argument(
        "--download-block-mib",
        type=int,
        default=1,
        help="Client download read block size in MiB (default: 1).",
    )
    parser.add_argument(
        "--csrf-cookie-name",
        default=os.environ.get("VITE_CSRF_COOKIE_NAME", "drivempvd_csrf"),
    )
    parser.add_argument(
        "--keep-entry",
        action="store_true",
        help=(
            "Keep the completed benchmark file instead of moving it to trash "
            "and deleting it."
        ),
    )
    return parser.parse_args()


def _configuration(arguments: argparse.Namespace) -> BenchmarkConfiguration:
    source_path = cast(Path, arguments.file).resolve()
    if not source_path.is_file():
        msg = f"Benchmark payload does not exist: {source_path}"
        raise ValueError(msg)
    if source_path.stat().st_size == 0:
        raise ValueError("Benchmark payload must not be empty.")
    chunk_mib = cast(int, arguments.chunk_mib)
    download_block_mib = cast(int, arguments.download_block_mib)
    if not 1 <= chunk_mib <= 16:
        raise ValueError("--chunk-mib must be between 1 and 16.")
    if download_block_mib <= 0:
        raise ValueError("--download-block-mib must be positive.")
    username = os.environ.get("DRIVEMPVD_BENCHMARK_USERNAME")
    password = os.environ.get("DRIVEMPVD_BENCHMARK_PASSWORD")
    if not username or not password:
        raise ValueError(
            "Set DRIVEMPVD_BENCHMARK_USERNAME and DRIVEMPVD_BENCHMARK_PASSWORD."
        )
    return BenchmarkConfiguration(
        base_url=cast(str, arguments.base_url).rstrip("/") + "/",
        api_prefix="/" + cast(str, arguments.api_prefix).strip("/"),
        chunk_size=chunk_mib * _MEBIBYTE,
        download_block_size=download_block_mib * _MEBIBYTE,
        csrf_cookie_name=cast(str, arguments.csrf_cookie_name),
        keep_entry=cast(bool, arguments.keep_entry),
        source_path=source_path,
        username=username,
        password=password,
    )


def _endpoint(configuration: BenchmarkConfiguration, path: str) -> str:
    return urljoin(configuration.base_url, configuration.api_prefix + path)


def _open(
    opener: OpenerDirector,
    request: Request,
) -> tuple[int, dict[str, str], bytes]:
    try:
        with opener.open(request, timeout=120) as response:
            return (
                response.status,
                dict(response.headers.items()),
                response.read(),
            )
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1024]
        raise BenchmarkRequestError(f"HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise BenchmarkRequestError("Could not reach the deployment.") from exc


def _json_request(
    opener: OpenerDirector,
    configuration: BenchmarkConfiguration,
    path: str,
    *,
    method: str,
    payload: dict[str, object] | None = None,
    csrf_token: str | None = None,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if csrf_token is not None:
        headers["X-CSRF-Token"] = csrf_token
    status, _headers, content = _open(
        opener,
        Request(
            _endpoint(configuration, path),
            data=body,
            headers=headers,
            method=method,
        ),
    )
    if not 200 <= status < 300:
        raise BenchmarkRequestError(f"Unexpected status {status} for {method} {path}.")
    try:
        response = json.loads(content)
    except json.JSONDecodeError as exc:
        message = f"Invalid JSON response for {method} {path}."
        raise BenchmarkRequestError(message) from exc
    if not isinstance(response, dict) or response.get("error") is not None:
        raise BenchmarkRequestError(f"API error response for {method} {path}.")
    data = response.get("data")
    if not isinstance(data, dict):
        raise BenchmarkRequestError(f"API data missing for {method} {path}.")
    return cast(dict[str, Any], data)


def _csrf_token(cookies: http.cookiejar.CookieJar, name: str) -> str:
    for cookie in cookies:
        if cookie.name == name:
            return str(cookie.value)
    raise BenchmarkRequestError("Login did not create the configured CSRF cookie.")


def _percentile(values: list[float], percentage: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _throughput(bytes_count: int, duration_seconds: float) -> float:
    return bytes_count / duration_seconds / _MEBIBYTE if duration_seconds > 0 else 0.0


def _upload(
    opener: OpenerDirector,
    configuration: BenchmarkConfiguration,
    csrf_token: str,
    parent_id: str,
) -> tuple[str, str, list[float], str]:
    size = configuration.source_path.stat().st_size
    suffix = configuration.source_path.suffix
    stem = configuration.source_path.stem[:180]
    filename = f"phase9-{uuid4()}-{stem}{suffix}"
    session = _json_request(
        opener,
        configuration,
        "/storage/uploads",
        method="POST",
        csrf_token=csrf_token,
        payload={
            "parent_id": parent_id,
            "filename": filename,
            "size": size,
            "mime_type": "application/octet-stream",
        },
    )
    upload_id = str(session["id"])
    chunk_latencies: list[float] = []
    offset = 0
    hasher = hashlib.sha256()
    try:
        with configuration.source_path.open("rb", buffering=0) as source:
            file_handle = cast(BinaryIO, source)
            while chunk := file_handle.read(configuration.chunk_size):
                hasher.update(chunk)
                started = time.perf_counter()
                _status, _headers, response = _open(
                    opener,
                    Request(
                        _endpoint(configuration, f"/storage/uploads/{upload_id}"),
                        data=chunk,
                        headers={
                            "Accept": "application/json",
                            "Content-Type": "application/offset+octet-stream",
                            "Upload-Offset": str(offset),
                            "X-CSRF-Token": csrf_token,
                        },
                        method="PATCH",
                    ),
                )
                chunk_latencies.append(time.perf_counter() - started)
                payload = json.loads(response)
                offset = int(payload["data"]["offset"])
        completed = _json_request(
            opener,
            configuration,
            f"/storage/uploads/{upload_id}/complete",
            method="POST",
            csrf_token=csrf_token,
        )
        return str(completed["id"]), upload_id, chunk_latencies, hasher.hexdigest()
    except Exception:
        with suppress(BenchmarkRequestError):
            _json_request(
                opener,
                configuration,
                f"/storage/uploads/{upload_id}",
                method="DELETE",
                csrf_token=csrf_token,
            )
        raise


def _download(
    opener: OpenerDirector,
    configuration: BenchmarkConfiguration,
    file_id: str,
) -> tuple[int, str, float, int]:
    request = Request(
        _endpoint(configuration, f"/storage/files/{file_id}/content"),
        headers={"Accept": "application/octet-stream"},
        method="GET",
    )
    started = time.perf_counter()
    hasher = hashlib.sha256()
    byte_count = 0
    try:
        with opener.open(request, timeout=120) as response:
            status = response.status
            while chunk := response.read(configuration.download_block_size):
                hasher.update(chunk)
                byte_count += len(chunk)
    except HTTPError as exc:
        raise BenchmarkRequestError(f"HTTP {exc.code} while downloading.") from exc
    return byte_count, hasher.hexdigest(), time.perf_counter() - started, status


def _range_status(
    opener: OpenerDirector,
    configuration: BenchmarkConfiguration,
    file_id: str,
) -> tuple[int, int]:
    status, _headers, content = _open(
        opener,
        Request(
            _endpoint(configuration, f"/storage/files/{file_id}/content"),
            headers={"Range": "bytes=0-1048575"},
            method="GET",
        ),
    )
    return status, len(content)


def _cleanup(
    opener: OpenerDirector,
    configuration: BenchmarkConfiguration,
    csrf_token: str,
    file_id: str,
) -> None:
    trash = _json_request(
        opener,
        configuration,
        f"/storage/entries/{file_id}/trash",
        method="POST",
        csrf_token=csrf_token,
    )
    _json_request(
        opener,
        configuration,
        f"/storage/trash/{trash['id']}",
        method="DELETE",
        csrf_token=csrf_token,
    )


def main() -> None:
    arguments = _parse_arguments()
    try:
        configuration = _configuration(arguments)
    except ValueError as exc:
        raise SystemExit(f"benchmark configuration error: {exc}") from exc

    cookies = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookies))
    login = _json_request(
        opener,
        configuration,
        "/auth/login",
        method="POST",
        payload={
            "username": configuration.username,
            "password": configuration.password,
            "delivery": "cookie",
        },
    )
    del login
    csrf_token = _csrf_token(cookies, configuration.csrf_cookie_name)
    navigation = _json_request(
        opener,
        configuration,
        "/storage/navigation",
        method="GET",
    )
    parent_id = str(navigation["folder"]["id"])

    file_id: str | None = None
    tracemalloc.start()
    upload_started = time.perf_counter()
    try:
        file_id, _upload_id, chunk_latencies, source_checksum = _upload(
            opener,
            configuration,
            csrf_token,
            parent_id,
        )
        upload_seconds = time.perf_counter() - upload_started
        downloaded, downloaded_checksum, download_seconds, _download_status = _download(
            opener,
            configuration,
            file_id,
        )
        range_status, range_bytes = _range_status(opener, configuration, file_id)
        if downloaded != configuration.source_path.stat().st_size:
            raise BenchmarkRequestError("Downloaded size differs from the source file.")
        if downloaded_checksum != source_checksum:
            msg = "Downloaded checksum differs from the uploaded bytes."
            raise BenchmarkRequestError(msg)
        if range_status != 206 or range_bytes != min(_MEBIBYTE, downloaded):
            raise BenchmarkRequestError("The one-MiB Range verification failed.")
        _current, peak = tracemalloc.get_traced_memory()
        report = {
            "source_file": str(configuration.source_path),
            "size_bytes": downloaded,
            "chunk_bytes": configuration.chunk_size,
            "upload_seconds": round(upload_seconds, 6),
            "upload_mib_per_second": round(_throughput(downloaded, upload_seconds), 2),
            "chunk_count": len(chunk_latencies),
            "chunk_latency_ms": {
                "p50": round(_percentile(chunk_latencies, 0.5) * 1000, 2),
                "p95": round(_percentile(chunk_latencies, 0.95) * 1000, 2),
                "p99": round(_percentile(chunk_latencies, 0.99) * 1000, 2),
                "mean": round(statistics.fmean(chunk_latencies) * 1000, 2),
            },
            "download_seconds": round(download_seconds, 6),
            "download_mib_per_second": round(
                _throughput(downloaded, download_seconds),
                2,
            ),
            "range_status": range_status,
            "range_bytes": range_bytes,
            "tracemalloc_peak_bytes": peak,
        }
        print(json.dumps(report, sort_keys=True))
    finally:
        tracemalloc.stop()
        if file_id is not None and not configuration.keep_entry:
            _cleanup(opener, configuration, csrf_token, file_id)


if __name__ == "__main__":
    try:
        main()
    except BenchmarkRequestError as exc:
        print(f"benchmark request error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
