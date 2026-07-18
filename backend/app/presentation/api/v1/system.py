"""System endpoints."""

from fastapi import APIRouter, Request, status

from app.application.use_cases.system import GetHealthUseCase
from app.presentation.schemas.envelope import ApiResponse, success_response
from app.presentation.schemas.system import HealthData


def create_system_router(get_health: GetHealthUseCase) -> APIRouter:
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

    return router
