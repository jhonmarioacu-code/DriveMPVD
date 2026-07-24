# Guía de desarrollo

## 1. Requisitos

| Área | Requisito |
| --- | --- |
| Backend | Python 3.13 compatible, pip y dependencias con hash. |
| Frontend | Node.js 22.12 o superior y npm 10 o superior. |
| Integración completa | Docker Engine y Docker Compose v2 sobre Ubuntu/Linux. |
| Base de datos | PostgreSQL 16 para integraciones reales. |

El runtime de contenedor objetivo es Python 3.13. No usar una prueba local con
otra versión como sustituto de la validación de runtime.

## 2. Estructura de trabajo

```text
backend/
  app/{domain,application,infrastructure,presentation,shared}
  alembic/
  tests/{unit,integration}
frontend/
  src/{app,features,pages,shared,styles,test}
docker/
scripts/
docs/
```

Lea [ARCHITECTURE.md](ARCHITECTURE.md) antes de mover módulos o introducir
dependencias entre capas.

## 3. Backend local

Desde `backend/`:

```bash
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps -e .
```

Puerta local:

```bash
python -m black --check app tests
python -m ruff check app tests
python -m mypy app tests
python -m pytest
```

Las pruebas que requieren PostgreSQL real están marcadas `postgresql`. No
interprete un skip por falta de base de datos como aprobación de integración.

## 4. Frontend local

Desde `frontend/`:

```powershell
npm ci
npm run dev
```

Vite escucha en `http://localhost:5173` y proxy `/api` al backend local en
`http://127.0.0.1:8000`. Producción usa `VITE_API_BASE_URL=/api/v1`.

Puerta frontend:

```powershell
npm run format
npm run lint
npm run typecheck
npm test
npm run build
```

La cobertura mínima configurada es 80 % para líneas, sentencias, funciones y
ramas. Los componentes no acceden a `fetch` directamente; usar los adaptadores
de feature sobre `shared/api`.

## 5. Convenciones

### Python

- Black, línea 88, Ruff y MyPy estricto.
- Módulos `snake_case`; clases `PascalCase`; tests `test_*.py`.
- DTOs/puertos en application; ORM/repositorios en infrastructure.
- No exponer modelos SQLAlchemy desde API ni dominio.
- Cada comando transaccional usa UoW y hace un único commit en el límite.

### TypeScript/React

- Archivos `kebab-case.tsx`; componentes `PascalCase`.
- Alias `@/` hacia `src`.
- Feature encapsula `api`, `model` y `ui`; exportar superficie pública mínima.
- Preferir TanStack Query para estado remoto e invalidar queries afectadas.
- No guardar JWT, contraseña o usuario en `localStorage`.
- Añadir pruebas de teclado, foco y ARIA cuando cambie UI interactiva.

### General

- Respetar `.editorconfig`: UTF-8, LF, final de archivo y espacios.
- No versionar secretos, caches, dependencias o runtime data.
- No mezclar cambios no relacionados.
- Actualizar la documentación temática y [CHANGELOG.md](CHANGELOG.md).

## 6. Migraciones

Con `DRIVEMPVD_DATABASE_URL`:

```bash
alembic upgrade head
alembic current
alembic check
```

Diseñe migraciones en esquema `expand → migrate → contract` cuando una
actualización no sea atómica. No use `alembic downgrade` como plan de
recuperación de producción; consulte [DATABASE.md](DATABASE.md) y
[BACKUP.md](BACKUP.md).

## 7. Cómo validar un cambio

| Cambio | Validación mínima |
| --- | --- |
| UI aislada | Frontend gate + prueba del componente/feature. |
| Contrato cliente/API | Frontend gate + test API/integación backend. |
| Dominio | Unit tests de invariantes y casos de uso. |
| Persistencia | PostgreSQL real, Alembic y suite host. |
| Upload/download | Tests storage, `HEAD`, Range, checksum y smoke autorizado. |
| Configuración | Compose config y preflight del entorno correspondiente. |

Los scripts y comandos de host se describen en [TESTING.md](TESTING.md) y
[DEPLOYMENT.md](DEPLOYMENT.md).

## 8. CI

`.github/workflows/ci.yml` ejecuta en push, pull request y ejecución manual:

1. sintaxis de shell, `docker/preflight.py` y contrato Compose;
2. scan de secretos/misconfiguración;
3. suite backend contra PostgreSQL;
4. suite frontend con formato, lint, tipos, tests, build y `npm audit`.

La CI no reemplaza validación de candidata, DNS/TLS, browser real, restore
offsite ni carga de host. Una modificación de scripts Docker o Compose debe
mantener estos jobs funcionales.

## 9. Documentar un cambio

Actualice un documento por responsabilidad, no todos:

- arquitectura: [ARCHITECTURE.md](ARCHITECTURE.md);
- API: [API.md](API.md);
- datos: [DATABASE.md](DATABASE.md);
- storage: [STORAGE.md](STORAGE.md);
- seguridad: [SECURITY.md](SECURITY.md);
- operaciones: [OPERATIONS.md](OPERATIONS.md);
- release/riesgo: [RELEASE.md](RELEASE.md).

Si un dato no está verificado, marque `[PENDIENTE]`; no rellene huecos con
suposiciones.
