"""OpenAPI security scheme augmentation derived from configured cookie name."""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def configure_auth_openapi(app: FastAPI, *, access_cookie_name: str) -> None:
    """Add Bearer and cookie alternatives to FastAPI-generated OpenAPI."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
            description=app.description,
        )
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
        security_schemes["AccessCookie"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": access_cookie_name,
        }
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
