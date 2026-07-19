# Fase 2.5: API REST de almacenamiento

- Estado: implementado y validado
- Fecha: 2026-07-18

## Entregado

- Adaptador FastAPI sin reglas de dominio en controladores.
- DTOs de aplicación independientes de entidades y esquemas Pydantic v2
  independientes del ORM.
- Read models para listado de hijos y detalle de archivo.
- Paginación keyset, orden ascendente/descendente y filtros combinables.
- Autenticación Bearer/cookie y CSRF reutilizados desde el middleware existente.
- Respuestas uniformes, errores globales y ejemplos OpenAPI.
- ETag, Last-Modified, If-None-Match e If-Modified-Since para metadatos.

## Endpoints

| Método | Ruta | Resultado |
|---|---|---|
| `GET` | `/api/v1/storage/navigation` | Raíz o breadcrumbs de una carpeta autorizada. |
| `GET` | `/api/v1/storage/folders/{folder_id}/entries` | Hijos directos paginados. |
| `GET` | `/api/v1/storage/files/{file_id}` | Metadatos del archivo. |
| `POST` | `/api/v1/storage/folders` | Crear carpeta. |
| `PATCH` | `/api/v1/storage/entries/{entry_id}` | Renombrar entrada. |
| `POST` | `/api/v1/storage/entries/{entry_id}/move` | Mover entrada. |
| `POST` | `/api/v1/storage/entries/{entry_id}/copy` | Copiar entrada. |
| `POST` | `/api/v1/storage/entries/{entry_id}/trash` | Enviar subárbol a papelera. |
| `POST` | `/api/v1/storage/trash/{trash_item_id}/restore` | Restaurar subárbol. |
| `DELETE` | `/api/v1/storage/trash/{trash_item_id}` | Eliminar metadatos definitivamente. |

El listado acepta `limit`, `cursor`, `sort_by`, `direction`, `name`, `kind`,
`extension`, `minimum_size`, `maximum_size`, `modified_from` y `modified_to`.
Los órdenes son `name`, `date`, `size` y `type`.

## OpenAPI

`GET /openapi.json` genera el contrato completo; `/docs` y `/redoc` lo
consumen. Incluye navegación, alternativas de seguridad Bearer/cookie,
schemas de petición/respuesta, ejemplos y respuestas de error/304. No se guarda
una copia JSON estática para evitar divergencias.

## Compatibilidad posterior

La Fase 5 añadió la revisión `20260718_0004`, que aprovisiona la raíz `Drive`
para administradores existentes que aún no la tengan. El bootstrap de nuevas
cuentas la crea en la misma transacción. También añadió
`GET /storage/navigation` para que el frontend pueda resolver la raíz y los
breadcrumbs sin inferirlos desde una carpeta conocida.

## Validación

| Control | Resultado |
|---|---|
| Black | 123 archivos sin cambios requeridos |
| Ruff | Sin incidencias |
| MyPy estricto | 123 archivos sin incidencias |
| Pytest | 81 pruebas superadas |
| Cobertura líneas/ramas | 91,53 %; mínimo 90 % |
| PostgreSQL | 16.14 real |
| Alembic | downgrade/upgrade/check sin drift |

## Riesgos y recomendaciones

- La raíz se aprovisiona internamente al crear la cuenta y se completa mediante
  migración; sigue sin exponerse un endpoint público de inicialización.
- Los listados son vivos, no snapshots: mutaciones concurrentes pueden cambiar
  la posición de una entrada entre páginas sin producir duplicados por offset.
- Las copias recursivas siguen siendo síncronas; aplicar el umbral/job definido
  en el incremento 2.4 antes de exponer carpetas enormes.
- Añadir `If-Match` y control de versión para evitar lost updates si en el
  futuro existen varios clientes concurrentes.
- Medir los cuatro órdenes con datos cercanos a producción; tamaño y tipo
  podrían requerir índices especializados según planes reales.
