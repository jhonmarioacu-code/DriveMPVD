# Estrategia de pruebas y calidad

## 1. Principios

Una capacidad no se considera terminada solo por compilar. Debe tener pruebas,
lint, formato, tipos, integración proporcional, documentación y evidencia.

PostgreSQL no se sustituye por SQLite para integración: locks, collations,
índices, constraints y extensiones son parte del producto.

## 2. Pirámide

| Nivel | Objetivo |
| --- | --- |
| Dominio | Invariantes y transiciones rápidas sin I/O. |
| Aplicación | Casos de uso, puertos fake, rollback y errores. |
| Infraestructura | PostgreSQL real, migraciones, filesystem temporal y adaptadores. |
| API | Contratos HTTP, auth, CSRF, errores, OpenAPI, `HEAD`/Range. |
| Frontend | Features, componentes, cliente HTTP y accesibilidad. |
| Smoke | Flujos autenticados contra Compose. |
| No funcional | Security scans, backup/restore, carga, UX y fallos de publicación. |

La suite E2E de navegador real está pendiente. La prueba visual manual tampoco
está reemplazada por Vitest.

## 3. Gates backend

Desde `backend/`:

```bash
python -m black --check app tests
python -m ruff check app tests
python -m mypy app tests
python -m pytest
```

Configuración vigente:

- MyPy strict.
- Black/Ruff con línea 88 y target Python 3.13.
- Pytest con cobertura de `app` y ramas.
- Umbral backend: 90 %.

Suite completa con PostgreSQL 16 aislado:

```bash
sudo sh docker/verify-postgresql-tests.sh
```

## 4. Gates frontend

Desde `frontend/`:

```powershell
npm run format
npm run lint
npm run typecheck
npm test
npm run build
```

El umbral frontend es 80 % para líneas, sentencias, funciones y ramas. El
script host `docker/verify-frontend.sh` añade build aislado y `npm audit`.

## 5. Casos obligatorios

- Traversal con Unicode, separadores, `.` y `..`.
- Conflictos/ciclos de mover, restaurar y copiar.
- Fallos entre blob y commit, idempotencia y outbox.
- Chunks truncados, repetidos, fuera de orden, excedidos y reanudados.
- `HEAD`, Range válido/múltiple/no satisfacible y condicionales.
- Inline solo para MIME seguro y fallback de descarga.
- Sesión expirada/revocada, refresh replay y CSRF ausente.
- Cursores/orden estable sin duplicados por `OFFSET`.
- Accesibilidad de teclado, foco, drawer, grid y responsive.
- Backup, restore, health, logs, scans y smoke antes de promoción.

## 6. Smoke de despliegue

```bash
export DRIVEMPVD_SMOKE_USERNAME=admin
export DRIVEMPVD_SMOKE_PASSWORD_FILE=/ruta/archivo-0600
sudo env DRIVEMPVD_COMPOSE_ENV_FILE=/etc/drivempvd/production.env \
  sh docker/verify-deployment.sh
```

El smoke escribe y limpia sus fixtures: carpeta, favorito, reciente, upload,
download, Range y papelera. Requiere entorno autorizado.

## 7. CI

La CI sobre Ubuntu 24.04 se ejecuta en push, pull request y manualmente. Sus
jobs validan contrato de deployment, source security, backend PostgreSQL y
frontend. Cualquier cambio en `docker/`, `scripts/`, Compose o dependencias debe
considerar los cuatro jobs.

## 8. Seguridad y recuperación

| Control | Procedimiento |
| --- | --- |
| Fuente | `sudo bash docker/verify-source-security.sh` |
| Imágenes | `sudo bash docker/verify-container-images.sh` |
| ZAP | `docker/verify-zap-baseline.sh` |
| Backup/restore | `docker/verify-backup-restore.sh` |
| Release health | `scripts/runtime/verify-release.sh` |

Vea [SECURITY.md](SECURITY.md) y [BACKUP.md](BACKUP.md).

## 9. Rendimiento

La prueba local de storage:

```bash
python backend/scripts/benchmark_storage.py --size-mib 256
```

La de 50 GiB requiere `--allow-large`, una ruta separada y autorización. El
benchmark autenticado debe registrar throughput, p50/p95/p99, checksum, Range,
CPU, RSS, I/O y concurrencia. Consulte [STORAGE.md](STORAGE.md) y
[RELEASE.md](RELEASE.md).

## 10. Evidencia consolidada

La candidata de julio de 2026 registró:

- 201 pruebas backend y 90,41 % de cobertura;
- 178 pruebas frontend en 26 archivos;
- 91,71 % statements, 81,95 % ramas, 90,42 % funciones y 93,60 % líneas;
- smoke autenticado, restore drill, scans y ZAP baseline aprobados;
- benchmark loopback de 256 MiB, no equivalente a SLO de Internet.

La línea base candidata reportó 127,65–132,76 MiB/s de escritura y
8.326,84–8.529,74 MiB/s de lectura caliente. El flujo autenticado de 256 MiB
reportó 110,0 MiB/s de subida, 221,09 MiB/s de descarga y p95 de chunks de
82 ms. Son mediciones loopback, no promesas de Internet.

Esta evidencia es histórica. Después de cambios se deben regenerar resultados,
no copiar cifras antiguas.

## 11. Pendientes

- E2E Playwright/Cypress.
- Validación visual real, consola y media en dispositivos.
- 50 GiB, concurrencia e Internet/TLS público.
- Criterios SLO/RPO/RTO aprobados.
