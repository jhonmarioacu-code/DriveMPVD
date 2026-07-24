# Informe de limpieza — DriveMPVD

## Alcance

Se revisaron archivos, carpetas, scripts y configuraciones del repositorio
fuera de dependencias de terceros. La revisión comprobó referencias en código
React/TypeScript, FastAPI/Python, Docker/Compose, Nginx, PostgreSQL, scripts y
CI antes de proponer eliminación. La consolidación documental y el detalle de
sus fuentes están en [DOCUMENTATION_AUDIT.md](DOCUMENTATION_AUDIT.md).

## Elementos eliminados

| Elemento | Motivo | Evidencia |
| --- | --- | --- |
| Documentación heredada indicada en `DOCUMENTATION_AUDIT.md` | Duplicada/dispersa; contenido útil consolidado en `docs/`. | Auditoría de 67 Markdown, mapeo de destino y validación de enlaces. |
| `backend/.mypy_cache/.gitignore` y `backend/.pytest_cache/README.md` | Metadatos de caché generados, sin contenido de producto. | Ambos pertenecían a cachés ignoradas por Git; no tienen consumidores de runtime. |

No se eliminó código de producto, Dockerfiles, configuraciones Nginx, scripts de
transferencia, scripts de benchmark, migraciones, tests, lockfiles, imágenes ni
datos de runtime.

## Elementos conservados

| Elemento | Motivo de conservación |
| --- | --- |
| `.github/workflows/ci.yml` | Ejecuta gates de deployment, seguridad, backend y frontend. |
| `docker/compose.accel.yaml` | Overlay futuro documentado y conservado deliberadamente; no está activado. |
| `docker/verify-*.sh`, `install-vps.sh`, `preflight.py` | Referenciados por tests, CI, release y operación. |
| `scripts/transfer/*.sh` y `Deploy-DriveMPVD.ps1` | Vías soportadas de staging/orquestación; tests las validan. |
| `backend/scripts/benchmark_*.py` | Herramientas de rendimiento usadas por documentación y tests. |
| `backend/.venv` | Entorno local de desarrollo activo; regenerable, pero eliminarlo interrumpiría validación local. |
| `frontend/node_modules` | Dependencias locales de desarrollo; regenerables mediante `npm ci`, no versionadas. |
| `backend/drivempvd_backend.egg-info` | Metadata de instalación editable local; regenerable, pero se conserva para no romper el entorno. |
| `.git` | Historial local; no es producto desplegable, pero es necesario para trazabilidad y release. |

## Artefactos generados conservados

| Elemento | Motivo de conservación temporal | Evidencia de que no es producto |
| --- | --- | --- |
| `backend/.mypy_cache` | Contiene una base binaria de análisis que el mecanismo de parche no puede borrar; la eliminación recursiva segura fue bloqueada por el entorno. | `.gitignore` y `push-rsync.sh` la excluyen; es salida de mypy. |
| `backend/.pytest_cache` | Conservada por la misma limitación de eliminación binaria/recursiva. | `.gitignore` y `push-rsync.sh` la excluyen; es salida de pytest. |
| `backend/.ruff_cache` | Conservada por la misma limitación de eliminación binaria/recursiva. | `.gitignore` y `push-rsync.sh` la excluyen; es salida de Ruff. |
| `backend/.coverage` | Base SQLite de cobertura no textual; no puede retirarse con parche textual en este entorno. | Ignorada por Git y generada por `pytest-cov`. |
| `frontend/coverage` | Incluye recursos binarios generados; no puede retirarse íntegramente con parche textual. | Ignorada por Git, excluida en transferencia y producida por `vitest run --coverage`. |
| `frontend/dist` | Es una salida local regenerable; se conservó al estar bloqueada la eliminación de directorio del entorno. | Ignorada por Git, excluida en transferencia y producida por `vite build`; Docker la construye dentro de su propia imagen. |
| `backend/**/__pycache__` y `docker/__pycache__` | 38 directorios, 199 archivos `.pyc` (1,82 MiB) generados; su borrado binario/recursivo fue bloqueado por el entorno. | `.gitignore` y `push-rsync.sh` excluyen `__pycache__` y `*.pyc`; no existen referencias consumidoras. |

Ninguno de estos elementos es un insumo de React, FastAPI, Docker, Nginx,
PostgreSQL o el despliegue. La evidencia de exclusión en los scripts de
transferencia confirma que tampoco forma parte de un release. Se conserva hasta
que se ejecute una eliminación local permitida; no debe añadirse a Git.

## Elementos no eliminados y por qué

- No se eliminan backups ni datos de VPS: no están dentro del workspace y su
  borrado requeriría autorización y restore probado.
- No se elimina el overlay `X-Accel-Redirect`: está deliberadamente reservado
  por diseño y documentación.
- No se elimina ninguna migración Alembic: las revisiones aplicadas son parte
  de la historia y recuperación de esquema.
- No se eliminan scripts de SCP/SFTP/rsync: están cubiertos por pruebas y
  soportan transporte de releases sin cambiar runtime activo.
- Los directorios locales vacíos `docs/adr` y `docs/increments` no contienen
  archivos y no son versionables en Git. Sus documentos fueron retirados; el
  entorno no permitió borrar los directorios físicos vacíos de forma separada.

## Recomendaciones

1. Mantener caches, coverage, `dist` y dependencias fuera de Git mediante
   `.gitignore`.
2. En una terminal local con permisos, eliminar únicamente los siete grupos de
   artefactos generados de la tabla anterior tras repetir la misma comprobación
   de rutas.
3. Limpiar solo paths generados y explícitamente verificados, nunca patrones
   amplios sobre storage, backups o el workspace.
4. Antes de borrar una herramienta aparentemente inactiva, buscar referencias
   en React, FastAPI, Compose, Nginx, tests, CI y documentos oficiales.
5. Ejecutar una comparación Local–Git–VPS nueva antes de producir un release,
   porque la reorganización documental cambió el contenido canónico.
