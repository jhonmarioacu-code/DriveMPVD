# Despliegue con Docker Compose

La composición de la raíz (`compose.yaml`) es el despliegue autocontenido de
DriveMPVD. Publica únicamente Nginx; PostgreSQL, FastAPI y el frontend están en
redes internas. El desarrollo con Vite y el backend local no cambia.

## Servicios

| Servicio   | Responsabilidad                                   | Red                |
| ---------- | ------------------------------------------------- | ------------------ |
| `nginx`    | Punto público, SPA, proxy `/api`, TLS y cabeceras | `edge` y `private` |
| `frontend` | Archivos estáticos construidos con Vite           | `edge`             |
| `api`      | FastAPI, autenticación, subidas y streaming       | `private`          |
| `migrate`  | Ejecuta `alembic upgrade head` antes de la API    | `private`          |
| `postgres` | PostgreSQL 16 con volumen nombrado                | `private`          |

No se declara un worker ficticio: todavía no hay un ejecutor de jobs de medios
en el backend. Se añadirá como servicio cuando exista un proceso real que pueda
reclamar y completar esos trabajos.

## Inicio HTTP local

En Linux o Ubuntu Server, desde la raíz del repositorio:

```bash
cp docker/.env.example docker/.env
mkdir -p data/storage docker/certificates docker/acme-webroot
docker compose --env-file docker/.env config
docker compose --env-file docker/.env up --build --wait -d
docker compose --env-file docker/.env run --rm api \
  python -m app.infrastructure.cli.create_admin admin
```

La aplicación queda disponible en `http://localhost:8080`. La configuración de
ejemplo usa cookies no `Secure` exclusivamente para este modo HTTP local; no se
debe exponer a Internet.

Para comprobar frontend, login, subida, descarga y una respuesta Range después
de crear el administrador:

```bash
export DRIVEMPVD_SMOKE_USERNAME=admin
export DRIVEMPVD_SMOKE_PASSWORD='la-contrasena-creada'
sh docker/verify-deployment.sh
```

El argumento `--start` de ese script valida Compose y levanta los servicios con
`--build --wait` antes de realizar las comprobaciones.

## Producción con HTTPS

1. Cree el directorio persistente y dé propiedad al UID no privilegiado de la
   API:

   ```bash
   sudo install -d -m 0750 -o 10001 -g 10001 /data/storage
   sudo install -d -m 0750 /var/lib/drivempvd/acme-webroot
   ```

2. Copie `docker/.env.production.example` a `docker/.env`. Reemplace todas las
   cadenas `replace-...` por secretos distintos de al menos 32 bytes y ajuste
   el DSN, el dominio de certificado y los puertos. Use, por ejemplo,
   `openssl rand -hex 48` para los tres secretos de autenticación.

3. Obtenga certificados con el método operativo elegido. Para Certbot en el
   host, arranque primero con `DRIVEMPVD_TLS_ENABLED=false`, utilice el webroot
   configurado en `DRIVEMPVD_ACME_WEBROOT_PATH`, y emita el certificado. Monte
   su directorio `live/<dominio>` en `DRIVEMPVD_TLS_CERTIFICATES_PATH`; debe
   contener `fullchain.pem` y `privkey.pem`.

4. Cambie `DRIVEMPVD_TLS_ENABLED=true` y `DRIVEMPVD_AUTH_COOKIE_SECURE=true`,
   después levante o recree el stack:

   ```bash
   docker compose --env-file docker/.env up --build --wait -d
   docker compose --env-file docker/.env ps
   ```

Nginx redirige HTTP a HTTPS, sirve el desafío ACME y emite HSTS sólo en el
servidor TLS. La API en modo `production` rechaza secretos o DSN de ejemplo y
cookies no `Secure` antes de arrancar.

## Streaming, subidas y X-Accel-Redirect

Nginx no publica el volumen de objetos en la configuración normal. `/api` se
mantiene en FastAPI, por lo que autorización, CSRF, `Content-Disposition`,
ETag, RFC 9110 y métricas continúan en el backend. Las rutas de chunks desactivan
el buffering de request/proxy; las de contenido preservan Range y no usan buffer
ni caché temporal. `DRIVEMPVD_NGINX_CLIENT_MAX_BODY_SIZE` debe permanecer al
menos tan alto como `DRIVEMPVD_MAX_UPLOAD_SIZE_BYTES`.

`docker/compose.accel.yaml` reserva una ubicación Nginx `internal` y monta el
almacenamiento de sólo lectura para una futura implementación de
`X-Accel-Redirect`. No lo active hasta que el adaptador del backend exista y se
hayan repetido las pruebas de rangos, ETag, `HEAD` y descarga autenticada:

```bash
docker compose --env-file docker/.env \
  -f compose.yaml -f docker/compose.accel.yaml up -d
```

## Operación básica

```bash
docker compose --env-file docker/.env logs -f nginx api migrate
docker compose --env-file docker/.env exec postgres pg_isready -U drivempvd -d drivempvd
docker compose --env-file docker/.env down
```

`down` conserva `postgres_data` y el directorio de objetos. Nunca use
`down --volumes` ni borre `/data/storage` sin un backup verificado.
