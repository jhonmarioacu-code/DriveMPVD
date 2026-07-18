from app.application.ports.file_storage import (
    ByteRangeDTO,
    StorageKey,
    StoredObjectDTO,
)


def test_storage_contract_uses_opaque_keys_and_ranges() -> None:
    byte_range = ByteRangeDTO(start=10, end=19)
    stored_object = StoredObjectDTO(key=StorageKey("opaque-key"), size=20)

    assert byte_range.start == 10
    assert byte_range.end == 19
    assert stored_object.key == "opaque-key"
    assert stored_object.size == 20
