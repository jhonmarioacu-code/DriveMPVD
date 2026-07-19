import hashlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.dtos.auth import BootstrapAdminCommandDTO
from app.domain.storage.entities import File, FileVersion, StorageObject
from app.domain.storage.enums import StorageObjectStatus
from app.infrastructure.bootstrap import create_application
from app.infrastructure.config.settings import AppEnvironment, Settings
from app.infrastructure.container import ApplicationContainer
from app.infrastructure.persistence.identifiers import Uuid7Generator

pytestmark = pytest.mark.postgresql


@dataclass(slots=True)
class StorageApiContext:
    client: AsyncClient
    container: ApplicationContainer
    root_id: UUID
    file_id: UUID
    headers: dict[str, str]
    storage_root: Path


@pytest.fixture
async def storage_api_context(
    migrated_database_url: str,
    clean_storage: None,
    tmp_path: Path,
) -> AsyncIterator[StorageApiContext]:
    del clean_storage
    settings = Settings(
        environment=AppEnvironment.TEST,
        database_url=migrated_database_url,
        storage_root=tmp_path / "storage",
        max_upload_size_bytes=8 * 1024 * 1024,
        max_upload_chunk_size_bytes=2 * 1024 * 1024,
        upload_allowed_extensions=("pdf", "txt", "png"),
        database_pool_size=2,
        database_max_overflow=0,
        argon2_time_cost=1,
        argon2_memory_cost_kib=19_456,
        argon2_parallelism=1,
        jwt_access_secret="a" * 40,
        jwt_refresh_secret="b" * 40,
        auth_secret_pepper="c" * 40,
        auth_cookie_secure=False,
    )
    container = ApplicationContainer.build(settings)
    admin = await container.bootstrap_admin.execute(
        BootstrapAdminCommandDTO(
            username="Admin",
            password="correct horse battery staple",
        )
    )
    id_generator = Uuid7Generator()
    root_id, file_id = await _seed_storage(container, admin.id, id_generator)
    application = create_application(settings, container=container)
    transport = ASGITransport(app=application, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "Admin",
                "password": "correct horse battery staple",
                "delivery": "bearer",
            },
        )
        token = login.json()["data"]["access_token"]
        yield StorageApiContext(
            client=client,
            container=container,
            root_id=root_id,
            file_id=file_id,
            headers={"Authorization": f"Bearer {token}"},
            storage_root=settings.storage_root,
        )
    await container.database.dispose()


async def _seed_storage(
    container: ApplicationContainer,
    owner_id: UUID,
    id_generator: Uuid7Generator,
) -> tuple[UUID, UUID]:
    now = datetime.now(UTC)
    file_id = id_generator.new()
    object_id = id_generator.new()
    checksum = "c" * 64
    async with container.unit_of_work_factory() as unit_of_work:
        path = await unit_of_work.storage.get_folder_path(
            owner_id=owner_id,
            folder_id=None,
        )
        root_id = path[-1].id
        await unit_of_work.storage.add_storage_object(
            StorageObject(
                id=object_id,
                storage_key=f"objects/{object_id}",
                size=2048,
                mime_type="application/pdf",
                checksum_sha256=checksum,
                status=StorageObjectStatus.READY,
                created_at=now,
                updated_at=now,
            )
        )
        file = File(
            id=file_id,
            owner_id=owner_id,
            parent_id=root_id,
            name="report.pdf",
            normalized_name="report.pdf",
            original_name="report.pdf",
            internal_name=f"{file_id}.pdf",
            size=2048,
            mime_type="application/pdf",
            extension="pdf",
            checksum_sha256=checksum,
            current_version_number=1,
            created_at=now,
            updated_at=now,
        )
        await unit_of_work.storage.add_file(
            file,
            FileVersion(
                id=id_generator.new(),
                file_id=file_id,
                storage_object_id=object_id,
                version_number=1,
                original_name=file.original_name,
                size=file.size,
                mime_type=file.mime_type,
                extension=file.extension,
                checksum_sha256=file.checksum_sha256,
                created_by=owner_id,
                created_at=now,
            ),
        )
        await unit_of_work.commit()
    return root_id, file_id


async def _create_folder(context: StorageApiContext, name: str) -> dict[str, object]:
    response = await context.client.post(
        "/api/v1/storage/folders",
        headers=context.headers,
        json={"parent_id": str(context.root_id), "name": name},
    )
    assert response.status_code == 201
    assert response.headers["Location"].endswith(
        f"/api/v1/storage/folders/{response.json()['data']['id']}/entries"
    )
    return cast(dict[str, object], response.json()["data"])


async def _upload_completed_file(
    context: StorageApiContext,
    *,
    filename: str,
    content: bytes,
    mime_type: str,
) -> dict[str, object]:
    started = await context.client.post(
        "/api/v1/storage/uploads",
        headers=context.headers,
        json={
            "parent_id": str(context.root_id),
            "filename": filename,
            "size": len(content),
            "mime_type": mime_type,
        },
    )
    assert started.status_code == 201
    upload_id = started.json()["data"]["id"]
    offset = 0
    while offset < len(content):
        chunk = content[offset : offset + 1024 * 1024]
        appended = await context.client.patch(
            f"/api/v1/storage/uploads/{upload_id}",
            headers={
                **context.headers,
                "Upload-Offset": str(offset),
                "Content-Type": "application/offset+octet-stream",
            },
            content=chunk,
        )
        assert appended.status_code == 200
        offset += len(chunk)
    completed = await context.client.post(
        f"/api/v1/storage/uploads/{upload_id}/complete",
        headers=context.headers,
    )
    assert completed.status_code == 201
    return cast(dict[str, object], completed.json()["data"])


async def test_storage_routes_require_auth_and_publish_openapi_contract(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    unauthorized = await context.client.get(
        f"/api/v1/storage/folders/{context.root_id}/entries"
    )
    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "auth.authentication_required"

    schema = (await context.client.get("/openapi.json")).json()
    paths = schema["paths"]
    expected = {
        "/api/v1/storage/navigation",
        "/api/v1/storage/folders/{folder_id}/entries",
        "/api/v1/storage/files/{file_id}",
        "/api/v1/storage/files/{file_id}/content",
        "/api/v1/storage/folders",
        "/api/v1/storage/entries/{entry_id}",
        "/api/v1/storage/entries/{entry_id}/move",
        "/api/v1/storage/entries/{entry_id}/copy",
        "/api/v1/storage/entries/{entry_id}/trash",
        "/api/v1/storage/trash/{trash_item_id}/restore",
        "/api/v1/storage/trash/{trash_item_id}",
        "/api/v1/storage/uploads",
        "/api/v1/storage/uploads/{upload_id}",
        "/api/v1/storage/uploads/{upload_id}/complete",
    }
    assert expected <= paths.keys()
    operation = paths["/api/v1/storage/folders"]["post"]
    assert operation["security"] == [{"BearerAuth": []}, {"AccessCookie": []}]
    assert operation["parameters"][0]["name"] == "X-CSRF-Token"
    schemas = schema["components"]["schemas"]
    assert schemas["CreateFolderInput"]["examples"]
    assert schemas["FileDetailsData"]["examples"]
    chunk_operation = paths["/api/v1/storage/uploads/{upload_id}"]["patch"]
    assert (
        "application/offset+octet-stream" in chunk_operation["requestBody"]["content"]
    )


async def test_navigation_resolves_provisioned_root_and_folder_breadcrumbs(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    root = await context.client.get(
        "/api/v1/storage/navigation",
        headers=context.headers,
    )
    assert root.status_code == 200
    assert root.json()["data"] == {
        "folder": {
            "id": str(context.root_id),
            "parent_id": None,
            "kind": "folder",
            "name": "Drive",
            "size": None,
            "mime_type": None,
            "extension": None,
            "checksum_sha256": None,
            "current_version_number": None,
            "created_at": root.json()["data"]["folder"]["created_at"],
            "updated_at": root.json()["data"]["folder"]["updated_at"],
        },
        "breadcrumbs": [{"id": str(context.root_id), "name": "Drive"}],
    }

    child = await _create_folder(context, "Documents")
    nested = await context.client.get(
        "/api/v1/storage/navigation",
        headers=context.headers,
        params={"folder_id": str(child["id"])},
    )
    assert nested.status_code == 200
    assert nested.json()["data"]["folder"]["id"] == child["id"]
    assert nested.json()["data"]["breadcrumbs"] == [
        {"id": str(context.root_id), "name": "Drive"},
        {"id": child["id"], "name": "Documents"},
    ]

    missing = await context.client.get(
        "/api/v1/storage/navigation",
        headers=context.headers,
        params={"folder_id": str(context.file_id)},
    )
    assert missing.status_code == 404


async def test_list_endpoint_paginates_sorts_filters_and_revalidates_cache(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    await _create_folder(context, "Zebra")
    await _create_folder(context, "Alpha")

    first = await context.client.get(
        f"/api/v1/storage/folders/{context.root_id}/entries",
        headers=context.headers,
        params={"limit": 2, "sort_by": "name", "direction": "asc"},
    )
    assert first.status_code == 200
    assert [item["name"] for item in first.json()["data"]["items"]] == [
        "Alpha",
        "report.pdf",
    ]
    cursor = first.json()["meta"]["next_cursor"]
    assert cursor
    second = await context.client.get(
        f"/api/v1/storage/folders/{context.root_id}/entries",
        headers=context.headers,
        params={"limit": 2, "sort_by": "name", "direction": "asc", "cursor": cursor},
    )
    assert [item["name"] for item in second.json()["data"]["items"]] == ["Zebra"]
    assert second.json()["meta"]["next_cursor"] is None

    folders = await context.client.get(
        f"/api/v1/storage/folders/{context.root_id}/entries",
        headers=context.headers,
        params={"kind": "folder", "name": "a", "sort_by": "date", "direction": "desc"},
    )
    assert {item["name"] for item in folders.json()["data"]["items"]} == {
        "Alpha",
        "Zebra",
    }
    pdfs = await context.client.get(
        f"/api/v1/storage/folders/{context.root_id}/entries",
        headers=context.headers,
        params={"extension": ".PDF", "minimum_size": 1024, "maximum_size": 4096},
    )
    assert [item["name"] for item in pdfs.json()["data"]["items"]] == ["report.pdf"]
    by_size = await context.client.get(
        f"/api/v1/storage/folders/{context.root_id}/entries",
        headers=context.headers,
        params={"sort_by": "size", "direction": "desc"},
    )
    assert by_size.json()["data"]["items"][0]["name"] == "report.pdf"
    by_type = await context.client.get(
        f"/api/v1/storage/folders/{context.root_id}/entries",
        headers=context.headers,
        params={"sort_by": "type", "modified_from": "2020-01-01T00:00:00Z"},
    )
    assert [item["kind"] for item in by_type.json()["data"]["items"]] == [
        "file",
        "folder",
        "folder",
    ]

    cached = await context.client.get(
        f"/api/v1/storage/folders/{context.root_id}/entries",
        headers={**context.headers, "If-None-Match": first.headers["ETag"]},
        params={"limit": 2},
    )
    assert cached.status_code == 304
    assert cached.content == b""
    assert cached.headers["Cache-Control"].startswith("private")

    invalid = await context.client.get(
        f"/api/v1/storage/folders/{context.root_id}/entries",
        headers=context.headers,
        params={"minimum_size": 10, "maximum_size": 1},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "request.validation_error"
    invalid_cursor = await context.client.get(
        f"/api/v1/storage/folders/{context.root_id}/entries",
        headers=context.headers,
        params={"cursor": "not-a-valid-cursor"},
    )
    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json()["error"]["code"] == "application.validation_error"


async def test_file_details_supports_etag_and_last_modified(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    path = f"/api/v1/storage/files/{context.file_id}"
    result = await context.client.get(path, headers=context.headers)

    assert result.status_code == 200
    assert result.json()["data"]["checksum_sha256"] == "c" * 64
    assert result.headers["ETag"].startswith('"')
    assert result.headers["Last-Modified"].endswith("GMT")

    by_etag = await context.client.get(
        path,
        headers={**context.headers, "If-None-Match": f"W/{result.headers['ETag']}"},
    )
    assert by_etag.status_code == 304
    by_date = await context.client.get(
        path,
        headers={
            **context.headers,
            "If-Modified-Since": result.headers["Last-Modified"],
        },
    )
    assert by_date.status_code == 304

    not_a_file = await context.client.get(
        f"/api/v1/storage/files/{context.root_id}", headers=context.headers
    )
    assert not_a_file.status_code == 404


async def test_mutation_endpoints_execute_complete_storage_lifecycle(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    source = await _create_folder(context, "Source")
    destination = await _create_folder(context, "Destination")
    source_id = source["id"]
    destination_id = destination["id"]

    renamed = await context.client.patch(
        f"/api/v1/storage/entries/{source_id}",
        headers=context.headers,
        json={"name": "Renamed"},
    )
    assert renamed.status_code == 200
    moved = await context.client.post(
        f"/api/v1/storage/entries/{source_id}/move",
        headers=context.headers,
        json={"destination_folder_id": destination_id},
    )
    assert moved.json()["data"]["parent_id"] == destination_id

    copied = await context.client.post(
        f"/api/v1/storage/entries/{context.file_id}/copy",
        headers=context.headers,
        json={"destination_folder_id": destination_id, "name": "copy.pdf"},
    )
    assert copied.status_code == 201
    copied_id = copied.json()["data"]["id"]
    trashed = await context.client.post(
        f"/api/v1/storage/entries/{copied_id}/trash",
        headers=context.headers,
    )
    assert trashed.status_code == 200
    trash_id = trashed.json()["data"]["id"]

    restored = await context.client.post(
        f"/api/v1/storage/trash/{trash_id}/restore",
        headers=context.headers,
        json={"destination_folder_id": str(context.root_id)},
    )
    assert restored.json()["data"]["parent_id"] == str(context.root_id)
    trashed_again = await context.client.post(
        f"/api/v1/storage/entries/{copied_id}/trash",
        headers=context.headers,
    )
    deleted = await context.client.delete(
        f"/api/v1/storage/trash/{trashed_again.json()['data']['id']}",
        headers=context.headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_entries"] == 1

    conflict = await context.client.post(
        "/api/v1/storage/folders",
        headers=context.headers,
        json={"parent_id": str(context.root_id), "name": "Destination"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "storage.name_conflict"


async def test_cookie_authenticated_mutations_require_csrf(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    cookie_login = await context.client.post(
        "/api/v1/auth/login",
        json={
            "username": "Admin",
            "password": "correct horse battery staple",
            "delivery": "cookie",
        },
    )
    assert cookie_login.status_code == 200
    rejected = await context.client.post(
        "/api/v1/storage/folders",
        json={"parent_id": str(context.root_id), "name": "Cookie folder"},
    )
    assert rejected.status_code == 403

    csrf = context.client.cookies["drivempvd_csrf"]
    accepted = await context.client.post(
        "/api/v1/storage/folders",
        headers={"X-CSRF-Token": csrf},
        json={"parent_id": str(context.root_id), "name": "Cookie folder"},
    )
    assert accepted.status_code == 201


async def test_small_upload_resumes_hashes_and_publishes_atomically(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    content = b"%PDF-1.7\nstreamed document\n%%EOF"
    started = await context.client.post(
        "/api/v1/storage/uploads",
        headers=context.headers,
        json={
            "parent_id": str(context.root_id),
            "filename": "uploaded.pdf",
            "size": len(content),
            "mime_type": "application/pdf",
        },
    )
    assert started.status_code == 201
    upload_id = started.json()["data"]["id"]

    first = await context.client.patch(
        f"/api/v1/storage/uploads/{upload_id}",
        headers={
            **context.headers,
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
        },
        content=content[:12],
    )
    assert first.status_code == 200
    assert first.headers["Upload-Offset"] == "12"
    status_response = await context.client.head(
        f"/api/v1/storage/uploads/{upload_id}", headers=context.headers
    )
    assert status_response.status_code == 204
    assert status_response.headers["Upload-Offset"] == "12"

    wrong_offset = await context.client.patch(
        f"/api/v1/storage/uploads/{upload_id}",
        headers={
            **context.headers,
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
        },
        content=b"wrong",
    )
    assert wrong_offset.status_code == 409
    assert wrong_offset.headers["Upload-Offset"] == "12"
    resumed = await context.client.patch(
        f"/api/v1/storage/uploads/{upload_id}",
        headers={
            **context.headers,
            "Upload-Offset": "12",
            "Content-Type": "application/offset+octet-stream",
        },
        content=content[12:],
    )
    assert resumed.headers["Upload-Offset"] == str(len(content))

    completed = await context.client.post(
        f"/api/v1/storage/uploads/{upload_id}/complete",
        headers=context.headers,
    )
    assert completed.status_code == 201
    data = completed.json()["data"]
    assert data["size"] == len(content)
    assert data["mime_type"] == "application/pdf"
    assert data["checksum_sha256"] == hashlib.sha256(content).hexdigest()
    assert not list((context.storage_root / "staging").glob("*.part"))
    stored_objects = [
        path for path in (context.storage_root / "objects").rglob("*") if path.is_file()
    ]
    assert len(stored_objects) == 1
    assert stored_objects[0].read_bytes() == content


async def test_large_upload_uses_multiple_bounded_chunks(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    mebibyte = 1024 * 1024
    total_size = 5 * mebibyte
    started = await context.client.post(
        "/api/v1/storage/uploads",
        headers=context.headers,
        json={
            "parent_id": str(context.root_id),
            "filename": "large.txt",
            "size": total_size,
            "mime_type": "text/plain",
        },
    )
    upload_id = started.json()["data"]["id"]
    hasher = hashlib.sha256()
    offset = 0
    for _ in range(5):
        response = await context.client.patch(
            f"/api/v1/storage/uploads/{upload_id}",
            headers={
                **context.headers,
                "Upload-Offset": str(offset),
                "Content-Type": "application/offset+octet-stream",
            },
            content=_repeated_content(b"x" * 64 * 1024, 16),
        )
        assert response.status_code == 200
        offset += mebibyte
        hasher.update(b"x" * mebibyte)
        assert response.json()["data"]["offset"] == offset

    completed = await context.client.post(
        f"/api/v1/storage/uploads/{upload_id}/complete",
        headers=context.headers,
    )
    assert completed.status_code == 201
    assert completed.json()["data"]["size"] == total_size
    assert completed.json()["data"]["checksum_sha256"] == hasher.hexdigest()


async def test_cancelled_and_invalid_uploads_leave_no_staging_files(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    blocked = await context.client.post(
        "/api/v1/storage/uploads",
        headers=context.headers,
        json={
            "parent_id": str(context.root_id),
            "filename": "malware.exe",
            "size": 10,
            "mime_type": "application/octet-stream",
        },
    )
    assert blocked.status_code == 422
    too_large = await context.client.post(
        "/api/v1/storage/uploads",
        headers=context.headers,
        json={
            "parent_id": str(context.root_id),
            "filename": "large.txt",
            "size": 9 * 1024 * 1024,
            "mime_type": "text/plain",
        },
    )
    assert too_large.status_code == 422
    not_allowed = await context.client.post(
        "/api/v1/storage/uploads",
        headers=context.headers,
        json={
            "parent_id": str(context.root_id),
            "filename": "photo.jpg",
            "size": 10,
            "mime_type": "image/jpeg",
        },
    )
    assert not_allowed.status_code == 422

    started = await context.client.post(
        "/api/v1/storage/uploads",
        headers=context.headers,
        json={
            "parent_id": str(context.root_id),
            "filename": "cancel.txt",
            "size": 100,
            "mime_type": "text/plain",
        },
    )
    upload_id = started.json()["data"]["id"]
    appended = await context.client.patch(
        f"/api/v1/storage/uploads/{upload_id}",
        headers={
            **context.headers,
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
        },
        content=b"partial",
    )
    assert appended.status_code == 200
    cancelled = await context.client.delete(
        f"/api/v1/storage/uploads/{upload_id}", headers=context.headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert not list((context.storage_root / "staging").glob("*.part"))


async def test_upload_rejects_oversized_chunks_incomplete_and_mime_mismatch(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    started = await context.client.post(
        "/api/v1/storage/uploads",
        headers=context.headers,
        json={
            "parent_id": str(context.root_id),
            "filename": "fake.png",
            "size": 8,
            "mime_type": "image/png",
        },
    )
    upload_id = started.json()["data"]["id"]
    incomplete = await context.client.post(
        f"/api/v1/storage/uploads/{upload_id}/complete",
        headers=context.headers,
    )
    assert incomplete.status_code == 409
    oversized = await context.client.patch(
        f"/api/v1/storage/uploads/{upload_id}",
        headers={
            **context.headers,
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
        },
        content=b"%PDF-1.70",
    )
    assert oversized.status_code == 422
    status_response = await context.client.head(
        f"/api/v1/storage/uploads/{upload_id}", headers=context.headers
    )
    assert status_response.headers["Upload-Offset"] == "0"
    appended = await context.client.patch(
        f"/api/v1/storage/uploads/{upload_id}",
        headers={
            **context.headers,
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
        },
        content=b"%PDF-1.7",
    )
    assert appended.status_code == 200
    mismatch = await context.client.post(
        f"/api/v1/storage/uploads/{upload_id}/complete",
        headers=context.headers,
    )
    assert mismatch.status_code == 422
    assert list((context.storage_root / "staging").glob("*.part"))
    await context.client.delete(
        f"/api/v1/storage/uploads/{upload_id}", headers=context.headers
    )
    assert not list((context.storage_root / "staging").glob("*.part"))


async def test_full_download_and_head_return_safe_complete_headers(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    missing_physical = await context.client.get(
        f"/api/v1/storage/files/{context.file_id}/content",
        headers=context.headers,
    )
    assert missing_physical.status_code == 404
    assert missing_physical.json()["error"]["code"] == "storage.entry_not_found"
    content = b"%PDF-1.7\ncomplete streamed download\n%%EOF"
    file = await _upload_completed_file(
        context,
        filename="résumé.pdf",
        content=content,
        mime_type="application/pdf",
    )
    path = f"/api/v1/storage/files/{file['id']}/content"

    head = await context.client.head(path, headers=context.headers)
    assert head.status_code == 200
    assert head.content == b""
    assert head.headers["Accept-Ranges"] == "bytes"
    assert head.headers["Content-Length"] == str(len(content))
    assert head.headers["Content-Type"] == "application/pdf"
    assert head.headers["Content-Disposition"].startswith("attachment;")
    assert (
        "filename*=UTF-8''r%C3%A9sum%C3%A9.pdf" in head.headers["Content-Disposition"]
    )

    downloaded = await context.client.get(path, headers=context.headers)
    assert downloaded.status_code == 200
    assert downloaded.content == content
    assert downloaded.headers["ETag"] == head.headers["ETag"]
    assert downloaded.headers["Last-Modified"].endswith("GMT")
    assert downloaded.headers["Cache-Control"].startswith("private")
    assert downloaded.headers["X-Content-Type-Options"] == "nosniff"


async def test_inline_downloads_are_limited_to_safe_browser_media(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    pdf = await _upload_completed_file(
        context,
        filename="preview.pdf",
        content=b"%PDF-1.7\npreview\n%%EOF",
        mime_type="application/pdf",
    )
    pdf_path = f"/api/v1/storage/files/{pdf['id']}/content"

    inline_pdf = await context.client.head(
        pdf_path,
        headers=context.headers,
        params={"disposition": "inline"},
    )
    assert inline_pdf.status_code == 200
    assert inline_pdf.content == b""
    assert inline_pdf.headers["Content-Disposition"].startswith("inline;")

    binary = await _upload_completed_file(
        context,
        filename="archive.txt",
        content=b"not browser media",
        mime_type="application/octet-stream",
    )
    binary_path = f"/api/v1/storage/files/{binary['id']}/content"
    rejected_inline = await context.client.get(
        binary_path,
        headers=context.headers,
        params={"disposition": "inline"},
    )
    assert rejected_inline.status_code == 200
    assert rejected_inline.content == b"not browser media"
    assert rejected_inline.headers["Content-Disposition"].startswith("attachment;")


async def test_ranges_multipart_and_conditional_downloads(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    content = b"%PDF-1.7\n0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    file = await _upload_completed_file(
        context,
        filename="ranges.pdf",
        content=content,
        mime_type="application/pdf",
    )
    path = f"/api/v1/storage/files/{file['id']}/content"
    metadata = await context.client.head(path, headers=context.headers)
    etag = metadata.headers["ETag"]

    partial = await context.client.get(
        path,
        headers={**context.headers, "Range": "bytes=0-3"},
    )
    assert partial.status_code == 206
    assert partial.content == content[:4]
    assert partial.headers["Content-Range"] == f"bytes 0-3/{len(content)}"
    assert partial.headers["Content-Length"] == "4"
    suffix = await context.client.get(
        path,
        headers={**context.headers, "Range": "bytes=-5"},
    )
    assert suffix.content == content[-5:]

    multipart = await context.client.get(
        path,
        headers={**context.headers, "Range": "bytes=0-2,10-13"},
    )
    assert multipart.status_code == 206
    assert multipart.headers["Content-Type"].startswith("multipart/byteranges")
    assert int(multipart.headers["Content-Length"]) == len(multipart.content)
    assert f"Content-Range: bytes 0-2/{len(content)}".encode() in multipart.content
    assert content[:3] in multipart.content
    assert content[10:14] in multipart.content

    not_modified = await context.client.get(
        path,
        headers={**context.headers, "If-None-Match": f"W/{etag}"},
    )
    assert not_modified.status_code == 304
    by_date = await context.client.get(
        path,
        headers={
            **context.headers,
            "If-Modified-Since": metadata.headers["Last-Modified"],
        },
    )
    assert by_date.status_code == 304
    failed_match = await context.client.get(
        path,
        headers={**context.headers, "If-Match": '"stale"'},
    )
    assert failed_match.status_code == 412
    assert failed_match.json()["error"]["code"] == "http.precondition_failed"
    matched = await context.client.get(
        path,
        headers={**context.headers, "If-Match": etag},
    )
    assert matched.status_code == 200
    unsatisfied = await context.client.get(
        path,
        headers={**context.headers, "Range": "bytes=999999-1000000"},
    )
    assert unsatisfied.status_code == 416
    assert unsatisfied.headers["Content-Range"] == f"bytes */{len(content)}"
    assert unsatisfied.json()["error"]["code"] == "http.range_not_satisfiable"


async def test_empty_and_large_files_stream_without_special_buffers(
    storage_api_context: StorageApiContext,
) -> None:
    context = storage_api_context
    empty = await _upload_completed_file(
        context,
        filename="empty.txt",
        content=b"",
        mime_type="application/octet-stream",
    )
    empty_result = await context.client.get(
        f"/api/v1/storage/files/{empty['id']}/content",
        headers=context.headers,
    )
    assert empty_result.status_code == 200
    assert empty_result.headers["Content-Length"] == "0"
    assert empty_result.content == b""

    large_content = b"z" * (3 * 1024 * 1024)
    large = await _upload_completed_file(
        context,
        filename="large-download.txt",
        content=large_content,
        mime_type="text/plain",
    )
    large_result = await context.client.get(
        f"/api/v1/storage/files/{large['id']}/content",
        headers=context.headers,
    )
    assert large_result.status_code == 200
    assert large_result.headers["Content-Length"] == str(len(large_content))
    assert large_result.content == large_content


async def _repeated_content(block: bytes, repetitions: int) -> AsyncIterator[bytes]:
    for _ in range(repetitions):
        yield block
