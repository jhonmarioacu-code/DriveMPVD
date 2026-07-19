# Fase 2.2: persistencia asíncrona

- Estado: implementado y validado
- Fecha: 2026-07-18

## Resumen técnico

- PostgreSQL 16 mediante SQLAlchemy 2 asíncrono y asyncpg.
- Pool tipado/configurable, `statement_timeout`, UTC, pre-ping y cierre en lifespan.
- Puertos `UnitOfWork`, `UnitOfWorkFactory`, `OutboxRepository` e `IdGenerator`.
- Implementaciones SQLAlchemy sin imports de ORM en dominio o aplicación.
- Generador UUID v7 RFC 9562, monotónico y seguro entre threads; constraint DB.
- Auditoría `created_at`, `updated_at` y `deleted_at`, con trigger de actualización.
- Outbox transaccional como primer repositorio real, sin lógica de otros módulos.
- Filtrado y keyset pagination; ninguna consulta de colección queda sin límite.
- Endpoint `/api/v1/ready` generado en OpenAPI y respaldado por `SELECT 1`.

## Estructura añadida

```text
backend/
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 20260718_0001_create_outbox_events.py
├── app/
│   ├── application/
│   │   ├── dtos/outbox.py
│   │   └── ports/{database_health,identifiers,outbox_repository,unit_of_work}.py
│   └── infrastructure/persistence/
│       ├── database.py
│       ├── health.py
│       ├── identifiers.py
│       ├── unit_of_work.py
│       ├── models/{base,outbox}.py
│       └── repositories/outbox.py
└── tests/
    ├── integration/{conftest,test_persistence}.py
    └── unit/{application,infrastructure}/...
```

## Migraciones

| Revisión        | Descripción     | Upgrade                               | Downgrade                        |
| --------------- | --------------- | ------------------------------------- | -------------------------------- |
| `20260718_0001` | Outbox auditada | Tabla, trigger, constraints e índices | Elimina exactamente esos objetos |

La suite ejecuta `downgrade base`, `upgrade head` y `alembic check`. El check no
detectó operaciones pendientes entre metadata ORM y migración.

## Índices

| Índice                         | Razón                                         |
| ------------------------------ | --------------------------------------------- |
| PK `id`                        | Lookup directo por UUID v7                    |
| `pending_created_id` parcial   | Worker: pendientes activos en orden keyset    |
| `aggregate_created_id` parcial | Historial filtrado por aggregate sin borrados |
| `type_created_id` parcial      | Eventos por tipo y paginación estable         |
| `deleted_at` parcial           | Purga/mantenimiento solo sobre soft-deleted   |

Los índices incluyen los campos de orden para evitar sort adicional. Se
validarán con `EXPLAIN (ANALYZE, BUFFERS)` cuando exista volumen representativo.

## Transacciones y carga

El UoW comienza una transacción explícita. Todos sus repositorios comparten la
sesión, hacen `flush` cuando necesitan defaults/constraints y nunca `commit`.
Salir sin commit, una excepción o un rollback explícito descarta el conjunto
completo. Fallos SQLAlchemy se traducen a `PersistenceError` sanitizado.

La outbox no tiene relaciones, por lo que sus consultas generan una sola
sentencia y no pueden producir N+1. Para modelos futuros el estándar será
relaciones `lazy="raise"` y cargas explícitas según cardinalidad; la prueba de
repositorio deberá contar sentencias.

## Validación

Entorno de integración: PostgreSQL 16.14 real.

| Control                   | Resultado                          |
| ------------------------- | ---------------------------------- |
| Black                     | 67 archivos sin cambios requeridos |
| Ruff                      | Sin incidencias                    |
| MyPy estricto             | 67 archivos sin incidencias        |
| Pytest                    | 40 pruebas superadas               |
| Cobertura de líneas/ramas | 95,06 %; umbral 90 %               |
| Alembic                   | Downgrade/upgrade/check correctos  |

## Limitaciones y riesgos

- La outbox todavía no publica ni reclama eventos; no debe crecer sin worker y
  política de retención en un incremento posterior.
- UUID v7 es monotónico dentro de un proceso. La unicidad entre procesos depende
  de 74 bits aleatorios, como permite RFC 9562; el PK sigue siendo la defensa final.
- Los timestamps usan el reloj de PostgreSQL. El host debe mantener NTP y UTC.
- El trigger de `updated_at` es común; cada nueva tabla auditada deberá declarar
  su trigger en su propia migración.
- Un downgrade es reproducible pero puede destruir datos. En producción exige
  backup y procedimiento de rollback revisado.
- Los índices actuales responden al patrón outbox. No deben copiarse a futuros
  aggregates sin planes `EXPLAIN` y mediciones.

## Recomendaciones antes del siguiente incremento

1. Ejecutar PostgreSQL 16 mediante Compose y repetir esta suite en Linux/Python 3.13.
2. Mantener una migración por cambio coherente y `alembic check` en CI.
3. Diseñar el siguiente aggregate desde invariantes de dominio antes del ORM.
4. Añadir conteo de queries cuando aparezca la primera relación ORM.
