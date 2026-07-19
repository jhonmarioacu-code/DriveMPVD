# Fase 2.1: fundamento transversal del backend

- Estado: implementado y validado
- Fecha: 2026-07-18

## Alcance

- Proyecto Python tipado y dependencias estables/acotadas.
- `Settings` central desde variables `DRIVEMPVD_*`.
- Composition root exclusivo de infraestructura e inyección por constructor.
- Excepciones de dominio, aplicación e infraestructura con traducción global.
- Envelope JSON uniforme y `request_id` seguro.
- Logging estructurado JSON a stdout.
- Puerto streaming `FileStorageProvider` para local/S3/MinIO.
- DTO genérico de paginación y healthcheck funcional en `/api/v1/health`.
- Swagger UI/ReDoc derivados del OpenAPI de FastAPI.
- Prueba automática de dirección de dependencias Clean Architecture.

No incluye SQLAlchemy, migraciones, repositorios, catálogo, autenticación ni
almacenamiento local concreto. Esas capacidades se entregan en incrementos
posteriores de la Fase 2.

## Decisiones

La composición se hace antes de construir routers: presentation recibe el caso
de uso de health ya listo y no usa `Depends` como service locator. La excepción
de infraestructura se registra desde el composition root mediante un contrato
público, evitando que presentation importe infrastructure.

Las versiones resueltas quedan reproducibles en archivos lock con hashes. El
runtime final seguirá siendo Python 3.13 aunque la validación local también sea
compatible con Python 3.14.

## Validación

Validado localmente con Python 3.14.6, conservando target y runtime de producción
Python 3.13:

| Control                    | Resultado                                             |
| -------------------------- | ----------------------------------------------------- |
| Black                      | 43 archivos sin cambios requeridos                    |
| Ruff                       | Sin incidencias                                       |
| MyPy estricto              | 43 archivos sin incidencias                           |
| Pytest                     | 18 pruebas superadas                                  |
| Cobertura                  | 94,89 % con ramas; mínimo exigido 80 %                |
| Límites Clean Architecture | Prueba AST superada                                   |
| Lock de producción         | Instalación `--require-hashes` resuelta correctamente |

Versiones estables resueltas relevantes: FastAPI 0.139.2, SQLAlchemy 2.0.51,
Alembic 1.18.5, Pydantic 2.13.4 y asyncpg 0.31.0. PostgreSQL se integrará y
probará en su contenedor 16 en el siguiente incremento de persistencia.
