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

Instale Docker Engine y Compose v2 desde los paquetes aprobados para Ubuntu y
compruebe que el daemon está activo antes de clonar un release:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
docker version
docker compose version
```

El usuario operador debe tener autorización explícita para Docker. Trate esa
autorización como acceso de administrador al host; no agregue usuarios de
aplicación ni cuentas compartidas al grupo Docker. Abra en el firewall sólo
80/TCP y 443/TCP para producción, mantenga el reloj sincronizado y compruebe
espacio e inodos para `/data/storage` y `/var/lib/docker`.

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
no deben cambiar sin actualizar a la vez el build del frontend. Si la
contraseña PostgreSQL contiene caracteres reservados de URL, codifíquela en el
DSN; el preflight verifica que el usuario, contraseña y base del DSN coincidan
con las variables `POSTGRES_*` sin imprimirlas.

`DRIVEMPVD_IMAGE_TAG` identifica una imagen de release y permite conservar el
tag anterior para rollback de aplicación. El preflight rechaza `local`,
`latest` y otros tags flotantes conocidos, además de placeholders. El registro
de imágenes debe impedir que un tag de release se sobrescriba: el preflight no
puede demostrar por sí solo la inmutabilidad remota.

`DRIVEMPVD_STORAGE_STREAM_BLOCK_SIZE_BYTES` y
`DRIVEMPVD_STORAGE_WRITE_BUFFER_SIZE_BYTES` empiezan en 1 MiB. El segundo no
necesita coincidir con el chunk HTTP: coalesce fragmentos pequeños sin retener
el archivo completo. Sólo debe ajustarse tras medir el mismo volumen de
almacenamiento con el benchmark de Fase 9.

## Instalación inicial

Obtenga un tag de release en una ruta de host controlada, cree el directorio de
datos y configure un tag de imagen que no vaya a reutilizarse:

```bash
sudo install -d -m 0750 -o 10001 -g 10001 /data/storage
sudo install -d -m 0750 /var/lib/drivempvd/acme-webroot
sudo install -d -m 0750 /etc/drivempvd/tls
sudo git clone <origen-del-repositorio> /srv/drivempvd
cd /srv/drivempvd
sudo git checkout --detach <release-tag>
sudo chown -R "$USER":"$(id -gn)" /srv/drivempvd
cp docker/.env.production.example docker/.env
chmod 600 docker/.env
# Edite docker/.env: secretos, dominio, rutas y DRIVEMPVD_IMAGE_TAG.
# Materialice fullchain.pem y privkey.pem como se indica en “TLS y cabeceras”.
sudo python3 docker/preflight.py --env-file docker/.env
```

Después de superar el preflight, cree el administrador sin exponer su
contraseña en argumentos y compruebe el estado del stack:

```bash
docker compose --env-file docker/.env config --quiet
docker compose --env-file docker/.env up --build --wait -d
docker compose --env-file docker/.env run --rm api \
  python -m app.infrastructure.cli.create_admin admin
docker compose --env-file docker/.env ps
```

`migrate` ejecuta Alembic sin crear administradores ni contraseñas. El comando
de bootstrap sigue siendo interactivo para que la contraseña no aparezca en
argumentos ni logs.

## TLS y cabeceras

### Primera emisión

Antes del primer arranque no existen PEMs y el perfil de producción se niega a
arrancar sin TLS. Con DNS ya propagado, 80/TCP abierto y ningún proceso usando
ese puerto, emita el certificado inicial con Certbot en modo standalone:

```bash
sudo apt-get install -y certbot
sudo certbot certonly --standalone \
  --domain drive.example.com --email ops@example.com \
  --agree-tos --no-eff-email
sudo install -d -m 0750 /etc/drivempvd/tls
sudo cp -L /etc/letsencrypt/live/drive.example.com/fullchain.pem \
  /etc/drivempvd/tls/fullchain.pem
sudo cp -L /etc/letsencrypt/live/drive.example.com/privkey.pem \
  /etc/drivempvd/tls/privkey.pem
sudo chmod 0644 /etc/drivempvd/tls/fullchain.pem
sudo chmod 0600 /etc/drivempvd/tls/privkey.pem
```

Sustituya dominio y correo. No ponga esos PEM dentro del repositorio. Después
del primer arranque, configure Certbot para renovar con el autenticador
`webroot` de `/var/lib/drivempvd/acme-webroot` (por ejemplo,
`certbot reconfigure --cert-name drive.example.com --webroot -w
/var/lib/drivempvd/acme-webroot` si la versión instalada lo admite). Si se
mantiene `standalone`, la tarea de renovación debe detener Nginx antes y
arrancarlo después; no ejecute ambos sobre 80/TCP a la vez.

Con `DRIVEMPVD_TLS_ENABLED=true`, Nginx exige
`fullchain.pem` y `privkey.pem` en la ruta montada por
`DRIVEMPVD_TLS_CERTIFICATES_PATH`. El servidor de puerto 80 sirve
`/.well-known/acme-challenge/` desde
`DRIVEMPVD_ACME_WEBROOT_PATH` y redirige el resto a HTTPS. HSTS se emite sólo
en la respuesta TLS.

No monte directamente `/etc/letsencrypt/live/<dominio>`: los PEM de Certbot
son habitualmente symlinks hacia `archive/` y dejarían de resolverse dentro del
montaje del contenedor. Configure la ruta de producción como
`/etc/drivempvd/tls` y copie PEMs dereferenciados tras cada renovación:

```bash
sudo install -d -m 0750 /etc/drivempvd/tls
sudo install -m 0644 "$(readlink -f /etc/letsencrypt/live/<dominio>/fullchain.pem)" \
  /etc/drivempvd/tls/fullchain.pem
sudo install -m 0600 "$(readlink -f /etc/letsencrypt/live/<dominio>/privkey.pem)" \
  /etc/drivempvd/tls/privkey.pem
docker compose --env-file docker/.env exec -T nginx nginx -s reload
```

Pruebe `certbot renew --dry-run` y use un deploy hook que repita las copias y
la recarga. La configuración de Nginx falla de forma explícita si un entorno
`production` intenta arrancar sin TLS.

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
- Límite de conexiones separado para subidas lentas, límite de ocho conexiones
  de contenido por IP y rate limits para login, refresh y API general.

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
export DRIVEMPVD_BENCHMARK_PASSWORD_FILE=/run/user/"$(id -u)"/drivempvd-benchmark-password
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
export DRIVEMPVD_SMOKE_PASSWORD_FILE=/run/user/"$(id -u)"/drivempvd-smoke-password
sh docker/verify-deployment.sh
```

El archivo de contraseña debe tener permisos `0600` y no terminar en el
historial del shell. El smoke lo pasa por archivos temporales privados y stdin,
nunca como argumento de `python` o `curl`. Comprueba SPA, readiness, cabeceras,
atributos `HttpOnly`/`SameSite`/`Path` de cookies, login por cookies, CSRF
ausente, navegación, creación/renombrado/movimiento, subida reanudable, PDF
inline, descarga, `HEAD`, Range, limpieza y logout. En
producción con certificado válido, ajuste
`DRIVEMPVD_SMOKE_BASE_URL=https://drive.ejemplo.com` antes de ejecutarlo.

El smoke HTTP no sustituye la comprobación visual del navegador. En el host
real, abra imágenes, PDF, audio y vídeo desde el explorador; confirme zoom y
rotación de imagen, controles nativos de audio/vídeo, PDF inline, descarga de
tipos no previsualizables, navegación con breadcrumbs, selector múltiple y el
diseño a 320 px y escritorio. Anote navegador, resolución y cualquier error de
consola junto al resultado del smoke.

Los procedimientos de backup, restore drill, actualización, rollback, rotación
de secretos y mantenimiento están en la
[guía de mantenimiento](maintenance.md). No haga downgrade de Alembic ni borre
volúmenes sin una restauración ensayada.
