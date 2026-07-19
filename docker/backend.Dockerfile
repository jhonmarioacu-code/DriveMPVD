# syntax=docker/dockerfile:1
FROM python:3.13-slim-bookworm

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system --gid 10001 drivempvd \
    && useradd --system --uid 10001 --gid drivempvd --home-dir /app --no-create-home drivempvd

WORKDIR /app

COPY backend/requirements.lock /tmp/requirements.lock
RUN python -m pip install --require-hashes -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

COPY --chown=drivempvd:drivempvd backend/app /app/app
COPY --chown=drivempvd:drivempvd backend/alembic /app/alembic
COPY --chown=drivempvd:drivempvd backend/alembic.ini /app/alembic.ini

USER drivempvd

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
