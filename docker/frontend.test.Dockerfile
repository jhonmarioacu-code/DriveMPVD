# syntax=docker/dockerfile:1
FROM node:22.23.1-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2

WORKDIR /workspace/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci \
    && chown -R node:node /workspace

COPY --chown=node:node frontend/ ./

USER node

CMD ["npm", "test"]
