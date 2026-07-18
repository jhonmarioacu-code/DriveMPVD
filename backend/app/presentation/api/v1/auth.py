"""Single-administrator authentication endpoints."""

from dataclasses import dataclass

from fastapi import APIRouter, Request, Response

from app.application.dtos.auth import (
    AuthenticationResultDTO,
    LoginCommandDTO,
    RefreshCommandDTO,
)
from app.application.exceptions import AuthenticationError
from app.application.use_cases.auth import (
    LoginUseCase,
    LogoutUseCase,
    RefreshSessionUseCase,
    RevokeAllSessionsUseCase,
)
from app.presentation.auth import AuthCookiePolicy, request_metadata, require_principal
from app.presentation.schemas.auth import (
    AuthenticationData,
    LoginInput,
    RefreshInput,
    RevocationData,
    SessionData,
)
from app.presentation.schemas.envelope import ApiResponse, success_response

_AUTH_SECURITY: list[dict[str, list[str]]] = [
    {"BearerAuth": []},
    {"AccessCookie": []},
]


@dataclass(frozen=True, slots=True)
class AuthRouteUseCases:
    login: LoginUseCase
    refresh: RefreshSessionUseCase
    logout: LogoutUseCase
    revoke_all: RevokeAllSessionsUseCase


def create_auth_router(
    use_cases: AuthRouteUseCases,
    cookie_policy: AuthCookiePolicy,
) -> APIRouter:
    """Build authentication routes from dependencies composed in infrastructure."""
    router = APIRouter(prefix="/auth")

    @router.post(
        "/login",
        response_model=ApiResponse[AuthenticationData],
        summary="Authenticate the administrator",
    )
    async def login(
        payload: LoginInput,
        request: Request,
        response: Response,
    ) -> ApiResponse[AuthenticationData]:
        client_ip, user_agent = request_metadata(request)
        result = await use_cases.login.execute(
            LoginCommandDTO(
                username=payload.username,
                password=payload.password,
                client_ip=client_ip,
                user_agent=user_agent,
            )
        )
        _deliver_tokens(response, result, payload.delivery, cookie_policy)
        return success_response(
            _authentication_data(result, payload.delivery),
            request_id=request.state.request_id,
        )

    @router.post(
        "/refresh",
        response_model=ApiResponse[AuthenticationData],
        summary="Rotate the refresh token",
    )
    async def refresh(
        payload: RefreshInput,
        request: Request,
        response: Response,
    ) -> ApiResponse[AuthenticationData]:
        cookie_token = request.cookies.get(cookie_policy.refresh_name)
        refresh_token = cookie_token or payload.refresh_token
        if refresh_token is None:
            raise AuthenticationError()
        client_ip, user_agent = request_metadata(request)
        result = await use_cases.refresh.execute(
            RefreshCommandDTO(
                refresh_token=refresh_token,
                client_ip=client_ip,
                user_agent=user_agent,
                csrf_cookie=request.cookies.get(cookie_policy.csrf_name),
                csrf_header=request.headers.get(cookie_policy.csrf_header_name),
                used_cookie=cookie_token is not None,
            )
        )
        _deliver_tokens(response, result, payload.delivery, cookie_policy)
        return success_response(
            _authentication_data(result, payload.delivery),
            request_id=request.state.request_id,
        )

    @router.post(
        "/logout",
        response_model=ApiResponse[None],
        summary="Revoke the current session",
        openapi_extra={"security": _AUTH_SECURITY},
    )
    async def logout(request: Request, response: Response) -> ApiResponse[None]:
        principal = require_principal(request)
        client_ip, user_agent = request_metadata(request)
        await use_cases.logout.execute(
            principal,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        _clear_cookies(response, cookie_policy)
        return success_response(None, request_id=request.state.request_id)

    @router.post(
        "/sessions/revoke-all",
        response_model=ApiResponse[RevocationData],
        summary="Revoke every administrator session",
        openapi_extra={"security": _AUTH_SECURITY},
    )
    async def revoke_all(
        request: Request, response: Response
    ) -> ApiResponse[RevocationData]:
        principal = require_principal(request)
        client_ip, user_agent = request_metadata(request)
        count = await use_cases.revoke_all.execute(
            principal,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        _clear_cookies(response, cookie_policy)
        return success_response(
            RevocationData(revoked_sessions=count),
            request_id=request.state.request_id,
        )

    @router.get(
        "/session",
        response_model=ApiResponse[SessionData],
        summary="Get the authenticated administrator session",
        openapi_extra={"security": _AUTH_SECURITY},
    )
    async def session(request: Request) -> ApiResponse[SessionData]:
        principal = require_principal(request)
        return success_response(
            SessionData(
                admin_id=principal.admin_id,
                session_id=principal.session_id,
                username=principal.username,
            ),
            request_id=request.state.request_id,
        )

    return router


def _authentication_data(
    result: AuthenticationResultDTO,
    delivery: str,
) -> AuthenticationData:
    include_tokens = delivery == "bearer"
    return AuthenticationData(
        session_id=result.session_id,
        access_token=result.access_token.value if include_tokens else None,
        refresh_token=result.refresh_token.value if include_tokens else None,
        access_expires_at=result.access_token.expires_at,
        refresh_expires_at=result.refresh_token.expires_at,
    )


def _deliver_tokens(
    response: Response,
    result: AuthenticationResultDTO,
    delivery: str,
    policy: AuthCookiePolicy,
) -> None:
    if delivery != "cookie":
        return
    response.set_cookie(
        policy.access_name,
        result.access_token.value,
        max_age=policy.access_max_age,
        secure=policy.secure,
        httponly=True,
        samesite="lax",
        domain=policy.domain,
        path="/",
    )
    response.set_cookie(
        policy.refresh_name,
        result.refresh_token.value,
        max_age=policy.refresh_max_age,
        secure=policy.secure,
        httponly=True,
        samesite="strict",
        domain=policy.domain,
        path=policy.refresh_path,
    )
    response.set_cookie(
        policy.csrf_name,
        result.csrf_token,
        max_age=policy.refresh_max_age,
        secure=policy.secure,
        httponly=False,
        samesite="lax",
        domain=policy.domain,
        path="/",
    )


def _clear_cookies(response: Response, policy: AuthCookiePolicy) -> None:
    response.delete_cookie(policy.access_name, path="/", domain=policy.domain)
    response.delete_cookie(
        policy.refresh_name,
        path=policy.refresh_path,
        domain=policy.domain,
    )
    response.delete_cookie(policy.csrf_name, path="/", domain=policy.domain)
