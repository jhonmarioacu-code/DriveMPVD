# Despliegue y operación

## Topología implantada

```text
Internet
   |
Nginx (80/443, único puerto publicado)
   |-- frontend (SPA estática, red edge)
   `-- api (FastAPI, red private)
          |-- migrate (Alembic antes del arranque)
          `-- PostgreSQL 16 (red private, volumen nombrado)

Host: /data/storage -> api con UID/GID 10001
```

`compose.yaml` usa dos redes: `edge` comunica Nginx con el frontend y
`private` aísla API, migraciones y PostgreSQL. API, frontend y PostgreSQL no
publican puertos del host. El servicio `migrate` debe terminar correctamente
antes de que `api` se inicie.

No existe aún un worker de medios operativo; por eso no se publica un
contenedor vacío. Cuando se implemente el procesador durable, compartirá la
imagen de backend y accederá sólo a los volúmenes estrictamente necesarios.

## Requisitos de Ubuntu Server 24.04

- Docker Engine y el plugin Docker Compose v2 actuales.
- Un DNS que dirija el dominio a la IP del host antes de emitir certificados.
- Almacenamiento persistente fuera del árbol del repositorio, por defecto
  `/data/storage`.
- Un usuario con permisos para ejecutar Docker; los secretos no deben quedar en
  el historial del shell ni en el repositorio.

Prepare las rutas persistentes antes de arrancar producción:

```bash
sudo install -d -m 0750 -o 10001 -g 10001 /data/storage
sudo install -d -m 0750 /var/lib/drivempvd/acme-webroot
```

La API se ejecuta como UID/GID 10001, con filesystem de contenedor de sólo
lectura y `/tmp` temporal. PostgreSQL usa el volumen nombrado `postgres_data`.

## Configuración

Los ejemplos están en `docker/.env.example` (HTTP local) y
`docker/.env.production.example` (HTTPS de producción). Copie uno a
`docker/.env`, restrinja sus permisos y no lo agregue al control de versiones:

```bash
cp docker/.env.production.example docker/.env
chmod 600 docker/.env
```

Los secretos JWT y el pepper deben ser valores independientes de al menos
32 bytes; `openssl rand -hex 48` produce un valor adecuado. En `production`,
`Settings` rechaza los marcadores de ejemplo, DSN con `replace-...` y cookies
sin `Secure`.

`DRIVEMPVD_MAX_UPLOAD_SIZE_BYTES` y
`DRIVEMPVD_NGINX_CLIENT_MAX_BODY_SIZE` se configuran por separado y deben ser
coherentes. El valor inicial es 50 GiB. Los nombres de cookies y el prefijo API
no deben cambiar sin actualizar a la vez el build del frontend.

`DRIVEMPVD_STORAGE_STREAM_BLOCK_SIZE_BYTES` y
`DRIVEMPVD_STORAGE_WRITE_BUFFER_SIZE_BYTES` empiezan en 1 MiB. El segundo no
necesita coincidir con el chunk HTTP: coalesce fragmentos pequeños sin retener
el archivo completo. Sólo debe ajustarse tras medir el mismo volumen de
almacenamiento con el benchmark de Fase 9.

## Instalación inicial

```bash
docker compose --env-file docker/.env config
docker compose --env-file docker/.env up --build --wait -d
docker compose --env-file docker/.env run --rm api \
  python -m app.infrastructure.cli.create_admin admin
docker compose --env-file docker/.env ps
```

`migrate` ejecuta Alembic sin crear administradores ni contraseñas. El comando
de bootstrap sigue siendo interactivo para que la contraseña no aparezca en
argumentos ni logs.

## TLS y cabeceras

Con `DRIVEMPVD_TLS_ENABLED=true`, Nginx exige
`fullchain.pem` y `privkey.pem` en la ruta montada por
`DRIVEMPVD_TLS_CERTIFICATES_PATH`. El servidor de puerto 80 sirve
`/.well-known/acme-challenge/` desde
`DRIVEMPVD_ACME_WEBROOT_PATH` y redirige el resto a HTTPS. HSTS se emite sólo
en la respuesta TLS.

Nginx añade CSP con origen propio, `frame-ancestors 'self'`,
`X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: no-referrer` y Permissions Policy restrictiva. `SAMEORIGIN`
permite el iframe PDF autenticado de la SPA sin abrir framing por terceros.

## Transferencias grandes

- `client_max_body_size`: 50 GiB inicial, configurable en Nginx.
- Chunks de subida: `proxy_request_buffering off`, sin archivos temporales de
  proxy y timeouts de una hora.
- Descargas y streaming: sin proxy buffering/caché temporal, con cabeceras
  Range, ETag y condicionales conservadas hacia FastAPI.
- Límite de conexiones para contenido y rate limits separados para login,
  refresh y API general.

La ubicación `/_drivempvd_internal_storage/` es `internal`; no tiene volumen
en la composición normal ni puede solicitarse desde Internet. El overlay
`docker/compose.accel.yaml` sólo prepara un montaje de lectura para el futuro
adaptador `X-Accel-Redirect`; la entrega actual permanece deliberadamente en
FastAPI.

## Benchmark de transferencias grandes

Primero valide el adaptador local sin exponer datos ni tocar el catálogo. El
fixture se borra al terminar; una prueba de 50 GiB exige confirmación explícita
y espacio para el archivo más una reserva:

```bash
python backend/scripts/benchmark_storage.py --size-mib 256
python backend/scripts/benchmark_storage.py \
  --directory /data/bench --size-gib 50 --allow-large
```

Para el trayecto real, genere o coloque un payload en un volumen con capacidad
suficiente. Si fuente y almacenamiento comparten disco, reserve al menos 115
GiB para una prueba de 50 GiB. Después del bootstrap y con el stack activo:

```bash
export DRIVEMPVD_BENCHMARK_USERNAME=admin
export DRIVEMPVD_BENCHMARK_PASSWORD='contraseña-creada'
python3 backend/scripts/benchmark_deployment.py \
  --file /data/bench/phase9-50g.bin \
  --base-url https://drive.example.com
```

El script limpia el archivo remoto mediante papelera y borrado permanente por
defecto; use `--keep-entry` sólo si necesita inspeccionarlo. Ejecute primero un
cliente y luego varios procesos contra payloads distintos, y guarde el JSON de
cada ejecución junto con CPU, RSS, I/O de disco, `docker stats` y planes
`EXPLAIN (ANALYZE, BUFFERS)`. No active `X-Accel-Redirect` hasta comparar ambos
modos manteniendo autorización, ETag, `HEAD` y Range.

## Validación y mantenimiento

Tras el bootstrap, ejecute el smoke test autenticado:

```bash
export DRIVEMPVD_SMOKE_USERNAME=admin
export DRIVEMPVD_SMOKE_PASSWORD='contraseña-creada'
sh docker/verify-deployment.sh
```

Comprueba SPA, readiness, login por cookies, CSRF, subida reanudable de un
chunk, descarga y `Range: bytes=0-3`. En producción con certificado válido,
ajuste `DRIVEMPVD_SMOKE_BASE_URL=https://drive.ejemplo.com` antes de ejecutarlo.

Para actualización: haga backup de PostgreSQL y `/data/storage`, construya la
nueva imagen, ejecute `up --build --wait`, revise `migrate`, repita el smoke
test y conserve la imagen previa para rollback de aplicación. No haga
downgrade de Alembic ni borre volúmenes sin una restauración ensayada.
