from app.application.use_cases.system import GetHealthUseCase


async def test_get_health_returns_injected_service_metadata() -> None:
    use_case = GetHealthUseCase(service_name="test-drive", version="9.8.7")

    result = await use_case.execute()

    assert result.status == "ok"
    assert result.service == "test-drive"
    assert result.version == "9.8.7"
