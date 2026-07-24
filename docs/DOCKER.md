# Docker y Docker Compose

## 1. Composición

`compose.yaml` es la composición autocontenida de DriveMPVD.

| Servicio | Rol | Red |
| --- | --- | --- |
| `postgres-init` | Inicializa permisos del volumen PostgreSQL. | Sin red. |
| `postgres` | PostgreSQL 16. | `private` |
| `migrate` | `alembic upgrade head`. | `private` |
| `api` | FastAPI, auth, storage y streaming. | `private` |
| `worker` | Outbox de objetos huérfanos. | `private` |
| `frontend` | Build estático Vite. | `edge` |
| `nginx` | Borde, SPA, proxy, TLS y headers. | `edge` y `private` |

`migrate` y `postgres-init` deben terminar con código 0. API y worker dependen
de migración; Nginx depende de API/frontend sanos.

## 2. Aislamiento

- `private` es interna; PostgreSQL no publica puertos.
- Solo Nginx publica HTTP/HTTPS.
- API/worker comparten `/data/storage` con usuario no privilegiado.
- API, worker, frontend y PostgreSQL usan root filesystem readonly, tmpfs y
  límites de PIDs/recursos según Compose.
- Nginx conserva la capacidad mínima para escuchar puertos.

## 3. Entornos

| Archivo | Uso |
| --- | --- |
| `docker/.env.example` | HTTP local o staging desechable. |
| `docker/.env.production.example` | Plantilla de producción, nunca secretos reales. |
| `/etc/drivempvd/validation.env` | Candidata privada real. |
| `/etc/drivempvd/production.env` | Producción real protegida. |

No copie secretos reales a `docker/.env` ni al repositorio. Mantenga
`DRIVEMPVD_MAX_UPLOAD_SIZE_BYTES` y
`DRIVEMPVD_NGINX_CLIENT_MAX_BODY_SIZE` coherentes.

## 4. Inicio local HTTP

En Linux/Ubuntu:

```bash
cp docker/.env.example docker/.env
sudo install -d -m 0750 -o 10001 -g 10001 data/storage
mkdir -p docker/certificates docker/acme-webroot
docker compose --env-file docker/.env config --quiet
docker compose --env-file docker/.env up --build --wait -d
docker compose --env-file docker/.env run --rm api \
  python -m app.infrastructure.cli.create_admin admin
```

La URL local es `http://localhost:8080`. Este modo usa cookies no `Secure` y
no se debe exponer a Internet.

## 5. Operación básica

```bash
docker compose --env-file <archivo> logs -f nginx api worker migrate
docker compose --env-file <archivo> exec postgres pg_isready -U <usuario> -d <base>
docker compose --env-file <archivo> ps
```

`docker compose down` conserva `postgres_data` y storage. Nunca usar
`down --volumes` ni borrar `/data/storage` sin backup/restore verificado.

## 6. Validación

```bash
docker compose --env-file <archivo> -f compose.yaml config --quiet
sudo sh docker/verify-postgresql-tests.sh
sudo sh docker/verify-frontend.sh
sudo bash docker/verify-source-security.sh
sudo bash docker/verify-container-images.sh
```

Para smoke, backup y release, vea [TESTING.md](TESTING.md),
[BACKUP.md](BACKUP.md) y [DEPLOYMENT.md](DEPLOYMENT.md).

## 7. X-Accel-Redirect

`docker/compose.accel.yaml` monta storage de lectura en Nginx y prepara una
ubicación `internal`. No activarlo hasta que exista un adaptador de entrega que
mantenga autorización, `HEAD`, ETag y Range, con benchmark real.
