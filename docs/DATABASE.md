# PostgreSQL, modelo de datos y migraciones

## 1. Responsabilidad

PostgreSQL 16 conserva metadatos, catálogo lógico, sesiones, migraciones,
actividad, outbox y coordinación transaccional. No contiene blobs de usuario ni
publica un puerto al host en Compose.

La fuente de verdad de metadatos es PostgreSQL. Los bytes residen en
[STORAGE.md](STORAGE.md), pero la elegibilidad para su borrado se decide en
base de datos.

## 2. Acceso y arquitectura

- SQLAlchemy 2 async y asyncpg implementan persistencia.
- Cada comando de escritura abre un `UnitOfWork`.
- Los repositorios comparten una sola `AsyncSession` y no hacen commit propios.
- Puertos viven en `application`; ORM, mapping y repositorios viven en
  `infrastructure`.
- Los modelos ORM no salen de repositorios.
- Queries usan proyecciones de lectura y keyset; no reconstruyen aggregates
  cuando no es necesario.

El pool, timeouts, UTC, pre-ping y lifecycle se configuran centralmente.

## 3. Modelo de datos consolidado

| Entidad/tabla conceptual | Responsabilidad |
| --- | --- |
| `storage_entries` | Tabla común para nodos lógicos de archivo/carpeta. |
| `file_metadata` | Atributos específicos de archivos. |
| `storage_objects` | Contenido físico inmutable: key opaca, tamaño, MIME, SHA-256 y estado. |
| `file_versions` | Snapshot de metadatos que referencia un `StorageObject`. |
| `upload_sessions` | Tamaño, offset, destino, expiración y estado de upload. |
| `trash_items` | Tombstone de la raíz enviada a papelera y su contexto. |
| `thumbnails` / `previews` | Referencias de derivados regenerables. |
| `favorites` | Favorito idempotente por propietario y entrada. |
| `recent_opens` | Última apertura y contador por propietario/entrada. |
| `outbox_events` | Eventos durables para trabajo posterior. |
| `admin_account` / `auth_sessions` | Cuenta singleton, credenciales y sesiones revocables. |

Los nombres de tablas concretos deben verificarse contra migraciones/modelos
antes de crear una consulta nueva. No introducir SQL de aplicación que dependa
de tablas ajenas a su módulo.

## 4. Invariantes

- ID de aplicación UUID v7 e inmutable.
- Existe una raíz activa canónica por administrador; es carpeta y no puede
  renombrarse, moverse, copiarse ni eliminarse.
- Dos hijos activos de un padre no comparten `normalized_name`.
- `parent_id` es nulo solo para la raíz.
- Una carpeta no puede moverse a sí misma ni a un descendiente.
- `FileVersion` y `StorageObject` son inmutables.
- `size` es no negativo y checksum SHA-256 es canónico.
- Un `Favorite` es único por propietario/entrada; `RecentOpen` no genera una
  fila por cada apertura.
- La cuenta administrativa es singleton. No crear usuarios/roles adicionales.

## 5. Índices y consultas

| Necesidad | Estrategia |
| --- | --- |
| Hijos activos | Índice compuesto por padre, nombre normalizado e ID. |
| Listados estables | Keyset por campo de orden + UUID. |
| Papelera, favoritos, recientes y jobs | Índices parciales/por propietario y fecha según migraciones. |
| Búsqueda por nombre | `pg_trgm` sobre nombre normalizado; medir antes de ampliar índices. |

Los listados son vivos, no snapshots prolongados. Una mutación concurrente
puede cambiar la posición entre páginas; el cursor evita coste creciente de
`OFFSET`, no ofrece un snapshot transaccional.

Antes de añadir índice:

1. obtener `EXPLAIN (ANALYZE, BUFFERS)` con datos representativos;
2. medir coste de escritura y tamaño;
3. documentar la decisión;
4. añadir migración compatible y prueba de integración.

## 6. Migraciones Alembic

Con `DRIVEMPVD_DATABASE_URL`:

```bash
alembic upgrade head
alembic current
alembic check
```

Reglas:

- las migraciones son progresivas y revisadas;
- usar `expand → migrate → contract` si versiones de aplicación coexistirán;
- validar upgrade, drift y pruebas contra PostgreSQL 16;
- no editar una migración aplicada;
- no utilizar `alembic downgrade` en producción como rollback;
- crear backup verificado antes de cambio estructural.

Las revisiones históricas incluyen la base de outbox, storage, raíz canónica,
índices de derivados y actividad persistente. El estado actual debe obtenerse
con `alembic current`, no inferirse de documentos históricos.

## 7. Outbox y trabajo durable

La outbox confirma eventos con la misma transacción que el cambio de dominio.
El worker reclama eventos con `FOR UPDATE SKIP LOCKED` y handlers idempotentes.

Para la purga:

1. `storage.orphan_sweep_requested` inicia el barrido.
2. Se seleccionan objetos sin referencias desde `FileVersion`, `Thumbnail` o
   `Preview`.
3. Se elimina el metadata elegible y se crea
   `storage.object_delete_requested`.
4. Un segundo handler borra el byte de modo idempotente.

El sistema no tiene todavía DLQ, backoff exponencial ni política de retención.
No usar la outbox para transportar bytes de archivo.

## 8. Validación PostgreSQL

### Suite aislada

```bash
sudo sh docker/verify-postgresql-tests.sh
```

Este script crea PostgreSQL 16 temporal, ejecuta Black, Ruff, MyPy, Pytest y
`pip-audit`. No reutiliza el volumen de producción.

### Integridad operativa

| Validación | Evidencia requerida |
| --- | --- |
| Salud | `pg_isready` sano en el contenedor. |
| Migración | Head esperado y `alembic check` sin drift. |
| Backup | Dump restaurable en contenedor desechable. |
| Storage | Hashes y referencias comprobadas por restore drill/auditoría. |
| Índices/restricciones | Revisión en PostgreSQL real; no declarar éxito sin consulta/evidencia. |
| Outbox | Sin eventos pendientes inesperados tras los flujos auditados. |

La evidencia histórica reporta integridad correcta en una candidata, pero debe
repetirse tras cambios de datos, storage, worker o migraciones.

## 9. Problemas conocidos

- No hay política de retención/DLQ para la outbox.
- Las copias recursivas grandes pueden requerir job idempotente y umbral.
- No se han fijado todos los índices especulativos de orden; medir con dataset
  real antes de agregarlos.
- La búsqueda global de contenido no está implementada.

Para recuperación, consulte [BACKUP.md](BACKUP.md). Para endpoints, consulte
[API.md](API.md).
