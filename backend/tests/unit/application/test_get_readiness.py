import pytest

from app.application.exceptions import DependencyUnavailableError
from app.application.use_cases.system import GetReadinessUseCase


class FakeDatabaseHealth:
    def __init__(self, *, ready: bool) -> None:
        self._ready = ready

    async def is_ready(self) -> bool:
        return self._ready


async def test_readiness_reports_available_database() -> None:
    use_case = GetReadinessUseCase(FakeDatabaseHealth(ready=True))

    result = await use_case.execute()

    assert result.status == "ready"
    assert result.database == "available"


async def test_readiness_rejects_unavailable_database() -> None:
    use_case = GetReadinessUseCase(FakeDatabaseHealth(ready=False))

    with pytest.raises(DependencyUnavailableError):
        await use_case.execute()
