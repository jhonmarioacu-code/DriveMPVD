# Guía de mantenimiento y recuperación

Este runbook complementa [despliegue y operación](operations.md). Está pensado
para un host Ubuntu con Docker Engine y Compose v2, y no sustituye un ensayo de
restauración en un entorno aislado.

## Invariantes operativos

- El conjunto consistente es PostgreSQL más el árbol completo de
  `DRIVEMPVD_STORAGE_PATH`. Actualmente incluye `objects` y `staging`; no
  elimine staging manualmente porque aún no existe un worker de reconciliación
  desplegado.
- No cambie `COMPOSE_PROJECT_NAME` en una instalación existente: Compose
  calcularía un volumen de PostgreSQL diferente.
- Cada despliegue de producción usa un `DRIVEMPVD_IMAGE_TAG` inmutable. El tag
  `local` es exclusivamente para desarrollo y se sobrescribe al reconstruir.
- Los secretos se conservan en un gestor de secretos o un respaldo cifrado
  separado; no copie `docker/.env` a un backup ordinario ni lo incluya en logs.

## Copia de seguridad coordinada

Programe un backup al menos con el RPO acordado. Antes de automatizarlo, ejecute
este procedimiento manual y conserve la salida, los checksums y el resultado
del restore drill.

1. Prepare un destino local protegido y después replíquelo cifrado a un destino
   externo. El directorio debe tener espacio para PostgreSQL y todo
   `/data/storage`:

   ```bash
   backup_id="$(date -u +%Y%m%dT%H%M%SZ)"
   backup_root="/var/backups/drivempvd/$backup_id"
   sudo install -d -m 0700 -o "$(id -u)" -g "$(id -g)" "$backup_root"
   ```

2. Desde el checkout del release en ejecución, corte las nuevas escrituras. No
   ejecute actualizaciones ni purgas durante esta ventana:

   ```bash
   cd /srv/drivempvd
   docker compose --env-file docker/.env stop nginx api
   ```

3. Cree un dump PostgreSQL en formato custom y copie el árbol completo de
   almacenamiento. `--numeric-ids` conserva los propietarios de los datos:

   ```bash
   docker compose --env-file docker/.env exec -T postgres sh -c \
     'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
     > "$backup_root/database.dump"
   sudo rsync -aHAX --numeric-ids /data/storage/ "$backup_root/storage/"
   sha256sum "$backup_root/database.dump" > "$backup_root/database.dump.sha256"
   sudo sh -c 'cd "$1" && find storage -type f -print0 | sort -z | \
     xargs -0 sha256sum > storage.sha256' sh "$backup_root"
   ```

4. Arranque de nuevo los servicios y verifique que todos estén sanos antes de
   abandonar la ventana:

   ```bash
   docker compose --env-file docker/.env up -d --wait nginx api
   docker compose --env-file docker/.env ps
   ```

5. Valide el dump y los hashes antes de cifrar y replicar el resultado:

   ```bash
   pg_restore --list "$backup_root/database.dump" >/dev/null
   sha256sum --check "$backup_root/database.dump.sha256"
   sudo sh -c 'cd "$1" && sha256sum --check storage.sha256' sh "$backup_root"
   ```

Use una herramienta de cifrado administrada, por ejemplo una clave de `age` o
un repositorio de backups cifrado, y pruebe la recuperación de la clave. Defina
retención, destino offsite y responsable fuera del repositorio. No borre la
copia local hasta que la réplica cifrada y sus hashes estén confirmados.

## Ensayo de restauración

La primera restauración se realiza en otro host o con otro proyecto Compose y
una ruta de almacenamiento vacía. No ejecute estos pasos sobre el proyecto de
producción ni reutilice `/data/storage`.

1. Cree un archivo de entorno aislado a partir del de producción. Cambie como
   mínimo `COMPOSE_PROJECT_NAME`, `DRIVEMPVD_STORAGE_PATH`, puertos y tag de
   imagen. Para un drill HTTP local, cambie también `DRIVEMPVD_ENVIRONMENT` a
   `development`, `DRIVEMPVD_AUTH_COOKIE_SECURE=false` y
   `DRIVEMPVD_TLS_ENABLED=false`; conserve los secretos de producción sólo si
   necesita validar sesiones existentes.

   ```bash
   cp docker/.env.production.example docker/.env.restore
   restore_project=drivempvd-restore-20260719
   # Edite: COMPOSE_PROJECT_NAME=drivempvd-restore-20260719
   # Edite: DRIVEMPVD_STORAGE_PATH=/srv/drivempvd-restore/storage
   # Edite: DRIVEMPVD_HTTP_PORT=18080 y DRIVEMPVD_HTTPS_PORT=18443
   sudo install -d -m 0750 -o 10001 -g 10001 /srv/drivempvd-restore/storage
   ```

2. Verifique el material de backup y restaure primero los objetos bajo la ruta
   aislada. El directorio padre del manifiesto debe contener `storage/`:

   ```bash
   backup_root=/var/backups/drivempvd/<backup-id>
   pg_restore --list "$backup_root/database.dump" >/dev/null
   sudo rsync -aHAX --numeric-ids "$backup_root/storage/" \
     /srv/drivempvd-restore/storage/
   sudo sh -c 'cd /srv/drivempvd-restore && sha256sum --check "$1/storage.sha256"' \
     sh "$backup_root"
   ```

3. Inicie sólo PostgreSQL del proyecto aislado, importe el dump y después
   levante el resto. Las migraciones son hacia adelante; no ejecute downgrade
   como mecanismo de recuperación.

   ```bash
   restore_project=drivempvd-restore-20260719
   docker compose -p "$restore_project" --env-file docker/.env.restore up -d postgres
   docker compose -p "$restore_project" --env-file docker/.env.restore exec -T postgres sh -c \
     'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" \
       -d "$POSTGRES_DB"' < "$backup_root/database.dump"
   docker compose -p "$restore_project" --env-file docker/.env.restore up --build --wait -d
   ```

4. Ejecute el smoke test contra el puerto aislado y compruebe navegación,
   lectura de objetos preexistentes y una subida nueva. Registre fecha, tamaño,
   duración y errores como evidencia del RTO:

   ```bash
   export DRIVEMPVD_SMOKE_USERNAME=admin
   export DRIVEMPVD_SMOKE_PASSWORD_FILE=/run/user/"$(id -u)"/drivempvd-smoke-password
   export DRIVEMPVD_SMOKE_BASE_URL=http://127.0.0.1:18080
   sh docker/verify-deployment.sh
   ```

La restauración de producción sólo se autoriza después de un ensayo exitoso.
Si se requiere recuperación real, preserve una copia forense de los datos
actuales, restaure el backup elegido en una ruta verificada y aplique el mismo
smoke test antes de reabrir el servicio.

## Actualización y rollback

1. Elija un tag de release, registre el commit y haga una copia de seguridad
   verificada. Guarde los tags de imagen actualmente desplegados antes de
   construir una versión nueva.
2. Obtenga el release, actualice `DRIVEMPVD_IMAGE_TAG` a un valor inmutable y
   valide sin imprimir secretos:

   ```bash
   git fetch --tags
   git checkout --detach <release-tag>
   sudo python3 docker/preflight.py --env-file docker/.env
   docker compose --env-file docker/.env build --pull
   docker compose --env-file docker/.env up -d --wait
   ```

3. Ejecute `sh docker/verify-deployment.sh` y revise `migrate`, Nginx y API.
   Cualquier cambio de `VITE_*` exige reconstruir la imagen frontend.
4. Si una migración aún no comenzó, puede volver al checkout y al
   `DRIVEMPVD_IMAGE_TAG` previo, y ejecutar `up -d --no-build --wait`. Si una
   migración ya se aplicó, no haga `alembic downgrade` en producción: restaure
   el backup coordinado y use una versión de aplicación compatible con ese
   esquema.

Cambiar `POSTGRES_PASSWORD` en `.env` no modifica una base existente. Rote la
contraseña con `ALTER ROLE` dentro de PostgreSQL, actualice el DSN y la variable
del servicio en una ventana coordinada. Rotar secretos JWT o el pepper invalida
sesiones y refresh tokens; planifique el reingreso del administrador.

## Rutina de mantenimiento

Ejecute y registre estos controles al menos semanalmente, y antes de una
actualización:

```bash
cd /srv/drivempvd
docker compose --env-file docker/.env ps
docker compose --env-file docker/.env logs --since 24h --tail 200 nginx api
docker stats --no-stream
df -h /data/storage /var/lib/docker
df -i /data/storage /var/lib/docker
openssl x509 -checkend 2592000 -noout -in /etc/drivempvd/tls/fullchain.pem
docker compose --env-file docker/.env exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT relname, n_live_tup, n_dead_tup, last_autovacuum FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 20;"'
```

Como umbrales iniciales, investigue menos de 20 % de espacio libre, actúe con
urgencia por debajo de 10 %, y renueve o investigue certificados con menos de
30 días. Revise el crecimiento de `staging` y los eventos de purga; la versión
actual no tiene un worker que elimine automáticamente sesiones expiradas u
objetos huérfanos. No borre esos archivos manualmente: abra una incidencia y
conserve evidencia hasta disponer de un reconciliador soportado.

La decisión actual es mantener `X-Accel-Redirect` desactivado. Sólo se revisa
después de medir en el host objetivo subida/descarga/Range de 50 GiB,
concurrencia, autorización, ETag, `HEAD`, cancelación y memoria con ambos
modos. El overlay existente no activa esa entrega por sí mismo.
