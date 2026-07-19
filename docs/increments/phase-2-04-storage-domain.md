# Fase 2.4: dominio de almacenamiento

- Estado: implementado y validado
- Fecha: 2026-07-18

## Entregado

- Entidades `Folder`, `File`, `StorageObject`, `FileVersion`, `Thumbnail`,
  `Preview`, `UploadSession` y `TrashItem` sin dependencias de infraestructura.
- Value objects para nombre seguro y SHA-256 canónico.
- DTOs y casos de uso transaccionales para crear, renombrar, mover, copiar,
  enviar a papelera, restaurar y eliminar definitivamente.
- Puertos `FileStorageProvider`, `ThumbnailGenerator`, `PreviewGenerator`,
  `MetadataExtractor` y `VirusScanner`, todos compatibles con streaming.
- Repositorio SQLAlchemy asíncrono con mapeo explícito y CTE recursivos.
- Composition root actualizado; no se añadió ninguna ruta o esquema HTTP.

## Estructura añadida

```text
backend/
├── app/
│   ├── domain/storage/{entities,enums,exceptions,value_objects}.py
│   ├── application/
│   │   ├── dtos/storage.py
│   │   ├── ports/{storage_repository,media_processing}.py
│   │   └── use_cases/storage/actions.py
│   └── infrastructure/persistence/
│       ├── models/storage.py
│       └── repositories/storage.py
├── alembic/versions/20260718_0003_create_storage_domain.py
└── tests/{unit/domain, integration}/
```

## Migración

`20260718_0003_create_storage_domain` crea y revierte:

- `storage_entries`, `file_metadata`, `storage_objects`, `file_versions`;
- `thumbnails`, `previews`, `upload_sessions`, `trash_items`;
- constraints UUID v7, FK, checks, unicidad y triggers `updated_at`.

Índices y finalidad:

- hermano activo `(parent_id, normalized_name)`: unicidad y resolución de
  conflictos;
- hijos `(parent_id, normalized_name, id)`: listado ordenado futuro;
- `(owner_id, updated_at, id)`: recientes con cursor estable;
- `deleted_at` parcial: papelera y mantenimiento;
- metadatos por checksum/tamaño, MIME, extensión y tamaño: filtros futuros;
- objeto por checksum/tamaño: candidato a deduplicación, deliberadamente no
  único;
- objeto por estado/fecha: reconciliación y limpieza;
- versión por objeto: comprobación de referencias antes de borrar bytes;
- sesión por propietario/estado y expiración: reanudación y limpieza;
- papelera por propietario/fecha/id: paginación estable futura.

## Validación

| Control                | Resultado                           |
| ---------------------- | ----------------------------------- |
| Black                  | 115 archivos sin cambios requeridos |
| Ruff                   | Sin incidencias                     |
| MyPy estricto          | 115 archivos sin incidencias        |
| Pytest                 | 73 pruebas superadas                |
| Cobertura líneas/ramas | 91,77 %; mínimo 90 %                |
| PostgreSQL             | 16.14 real                          |
| Alembic                | downgrade/upgrade/check sin drift   |

## Riesgos y recomendaciones

- Ejecutar la misma suite en CI con Ubuntu 24.04 y Python 3.13; la validación
  local se hizo con Python 3.14 compatible con el target declarado.
- Crear la raíz en el flujo de aprovisionamiento antes de exponer comandos.
- Convertir copias/purgas de subárboles grandes en jobs con checkpoints.
- Implementar el consumidor de `storage.orphan_sweep_requested` antes de
  habilitar purga física.
- Medir CTE e índices con distribuciones cercanas a 500 000 archivos antes de
  cerrar la optimización.
