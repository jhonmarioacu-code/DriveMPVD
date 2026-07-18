"""System endpoints."""

from fastapi import APIRouter, Request, status

from app.application.use_cases.system import GetHealthUseCase, GetReadinessUseCase
from app.presentation.schemas.envelope import ApiResponse, success_response
from app.presentation.schemas.system import HealthData, ReadinessData


def create_system_router(
    get_health: GetHealthUseCase,
    get_readiness: GetReadinessUseCase,
) -> APIRouter:
    """Create system routes with an already-constructed use case."""
    router = APIRouter()

    @router.get(
        "/health",
        response_model=ApiResponse[HealthData],
        status_code=status.HTTP_200_OK,
        summary="Check API liveness",
    )
    async def get_health_status(request: Request) -> ApiResponse[HealthData]:
        result = await get_health.execute()
        data = HealthData(
            status=result.status,
            service=result.service,
            version=result.version,
        )
        return success_response(data, request_id=request.state.request_id)

    @router.get(
        "/ready",
        response_model=ApiResponse[ReadinessData],
        status_code=status.HTTP_200_OK,
        summary="Check API readiness",
    )
    async def get_readiness_status(request: Request) -> ApiResponse[ReadinessData]:
        result = await get_readiness.execute()
        data = ReadinessData(status=result.status, database=result.database)
        return success_response(data, request_id=request.state.request_id)

    return router
