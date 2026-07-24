# syntax=docker/dockerfile:1
FROM node:22.23.1-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_CSRF_COOKIE_NAME=drivempvd_csrf
ARG VITE_CSRF_HEADER_NAME=X-CSRF-Token
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_CSRF_COOKIE_NAME=${VITE_CSRF_COOKIE_NAME} \
    VITE_CSRF_HEADER_NAME=${VITE_CSRF_HEADER_NAME}

RUN npm run build

FROM nginx:1.30.4-alpine@sha256:97d490c12ba55b4946b01546d1c3ed324e8d41ab1c9fcb2a616aa470620e5b46 AS runtime

COPY docker/frontend/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html

RUN chown -R nginx:nginx /usr/share/nginx/html

USER nginx

EXPOSE 8080

ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
