# Fase 8: Docker Compose y Nginx

- Estado: cerrada por implementación; validación runtime pendiente de un host Docker
- Fecha: 2026-07-19

## Objetivo

Convertir la arquitectura prevista en un despliegue reproducible para Ubuntu
Server: imágenes de frontend y backend, PostgreSQL privado, migraciones
controladas, Nginx público, configuración de TLS y transferencias grandes sin
romper el desarrollo local.

## Implementación

- `compose.yaml` con `nginx`, `frontend`, `api`, `migrate` y `postgres`.
- Redes pública/privada, volumen PostgreSQL y bind mount de objetos con
  permisos de mínimo privilegio.
- Nginx con SPA fallback, proxy de API, cabeceras de seguridad, TLS activable,
  límites de subida, timeouts y rutas no bufferizadas para chunks/streaming.
- Ejemplos de entorno HTTP local y HTTPS de producción, más operación de
  bootstrap y prueba de humo autenticada.
- Preparación, sin activación, de la ubicación Nginx `internal` para una futura
  entrega mediante `X-Accel-Redirect`.

### Artefactos

- `compose.yaml`: cinco servicios, dos redes, migración previa a API, health
  checks y publicación exclusiva de Nginx.
- `docker/backend.Dockerfile`, `docker/frontend.Dockerfile` y
  `docker/nginx/Dockerfile`: imágenes reproducibles de Python 3.13, build de
  Vite y proxy Nginx respectivamente.
- `docker/nginx/`: selección explícita HTTP/HTTPS, TLS 1.2/1.3, SPA fallback,
  proxy de API, límites, timeouts, rate limits, cabeceras y rutas de streaming.
- `docker/.env.example` y `docker/.env.production.example`: configuración
  separada para HTTP local y HTTPS de producción.
- `docker/verify-deployment.sh`: smoke test autenticado de login, CSRF, subida,
  descarga, `Range` y cabeceras.
- `docker/compose.accel.yaml`: overlay opcional, de sólo lectura, reservado para
  el futuro adaptador `X-Accel-Redirect`.

La composición normal no monta objetos en el proxy y no activa
`X-Accel-Redirect`. La API mantiene la autorización y streaming RFC 9110 hasta
que se implemente y pruebe el adaptador correspondiente.

## Estado de validación

Ejecutado el 2026-07-19:

- Validación estática de YAML, dependencias de Compose, aislamiento de redes,
  montaje de almacenamiento, directivas Nginx, ejemplo de variables y contrato
  del smoke test: correcta (`deployment-static-contract-ok`).
- Backend: Ruff, Black y MyPy correctos; `pytest --no-cov` con 84 pruebas
  correctas y 27 omitidas por falta de PostgreSQL local. La ejecución con la
  puerta de cobertura produjo 62,24 %, por debajo del 90 % configurado, porque
  esas integraciones quedaron omitidas; no es una regresión introducida por
  este incremento.
- Frontend: TypeScript, ESLint, Prettier y build correctos; Vitest con
  161 pruebas correctas y 91,16 % de statements.

No fue posible ejecutar `docker compose config`, construir imágenes ni realizar
el smoke test de extremo a extremo: el entorno de trabajo no dispone de Docker
Engine, Docker Compose, Podman, Nginx ni WSL. El cierre operativo requiere un
host Ubuntu con Docker Compose y estos pasos:

```bash
cp docker/.env.example docker/.env
sudo install -d -m 0750 -o 10001 -g 10001 data/storage
mkdir -p docker/certificates docker/acme-webroot
docker compose --env-file docker/.env up --build --wait -d
docker compose --env-file docker/.env run --rm api \
  python -m app.infrastructure.cli.create_admin admin
DRIVEMPVD_SMOKE_USERNAME=admin \
DRIVEMPVD_SMOKE_PASSWORD_FILE=/run/user/"$(id -u)"/drivempvd-smoke-password \
  sh docker/verify-deployment.sh
```

La última orden verifica frontend, backend, base de datos, login, subida,
descarga, cabeceras y streaming Range. Para producción debe repetirse con TLS
real y `docker/.env.production.example` ya reemplazado por secretos seguros.

## Siguiente fase

La Fase 9 no se iniciará hasta dejar este incremento validado, documentado y
confirmado mediante commit.
