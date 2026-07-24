# syntax=docker/dockerfile:1
FROM python:3.13.14-slim-bookworm@sha256:9d7f287598e1a5a978c015ee176d8216435aaf335ed69ac3c38dd1bbb10e8d64

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace/backend

COPY backend/requirements-dev.lock /tmp/requirements-dev.lock
RUN python -m pip install --require-hashes -r /tmp/requirements-dev.lock \
    && rm /tmp/requirements-dev.lock \
    && groupadd --system --gid 10001 drivempvd \
    && useradd --system --uid 10001 --gid drivempvd --home-dir /workspace --no-create-home drivempvd

COPY --chown=drivempvd:drivempvd . /workspace

USER drivempvd

CMD ["python", "-m", "pytest"]
