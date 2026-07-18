"""ASGI entrypoint."""

from app.infrastructure.bootstrap import create_application

app = create_application()
