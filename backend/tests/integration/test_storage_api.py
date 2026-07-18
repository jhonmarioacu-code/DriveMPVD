from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.dtos.auth import BootstrapAdminCommandDTO
from app.domain.storage.entities import File, FileVersion, Folder, StorageObject
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


@pytest.fixture
async def storage_api_context(
    migrated_database_url: str,
    clean_storage: None,
) -> AsyncIterator[StorageApiContext]:
    del clean_storage
    settings = Settings(
        environment=AppEnvironment.TEST,
        database_url=migrated_database_url,
        storage_root=Path.cwd().anchor,
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
        )
    await container.database.dispose()


async def _seed_storage(
    container: ApplicationContainer,
    owner_id: UUID,
    id_generator: Uuid7Generator,
) -> tuple[UUID, UUID]:
    now = datetime.now(UTC)
    root_id = id_generator.new()
    file_id = id_generator.new()
    object_id = id_generator.new()
    checksum = "c" * 64
    async with container.unit_of_work_factory() as unit_of_work:
        await unit_of_work.storage.add_folder(
            Folder(
                id=root_id,
                owner_id=owner_id,
                parent_id=None,
                name="Drive",
                normalized_name="drive",
                created_at=now,
                updated_at=now,
            )
        )
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
        "/api/v1/storage/folders/{folder_id}/entries",
        "/api/v1/storage/files/{file_id}",
        "/api/v1/storage/folders",
        "/api/v1/storage/entries/{entry_id}",
        "/api/v1/storage/entries/{entry_id}/move",
        "/api/v1/storage/entries/{entry_id}/copy",
        "/api/v1/storage/entries/{entry_id}/trash",
        "/api/v1/storage/trash/{trash_item_id}/restore",
        "/api/v1/storage/trash/{trash_item_id}",
    }
    assert expected <= paths.keys()
    operation = paths["/api/v1/storage/folders"]["post"]
    assert operation["security"] == [{"BearerAuth": []}, {"AccessCookie": []}]
    assert operation["parameters"][0]["name"] == "X-CSRF-Token"
    schemas = schema["components"]["schemas"]
    assert schemas["CreateFolderInput"]["examples"]
    assert schemas["FileDetailsData"]["examples"]


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
