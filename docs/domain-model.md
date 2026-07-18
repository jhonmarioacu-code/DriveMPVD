# Modelo de dominio

Este documento define conceptos y restricciones; no es todavía un esquema ORM.

## Aggregate `Entry`

Representa un archivo o carpeta en el árbol lógico.

| Concepto | Regla |
|---|---|
| `EntryId` | UUID generado por la aplicación, inmutable |
| `parent_id` | Carpeta padre; nulo solo para la raíz canónica |
| `kind` | `file` o `folder`, nunca inferido de la extensión |
| `name` | Nombre visible validado; no contiene separadores ni segmentos `.`/`..` |
| `normalized_name` | Forma normalizada para unicidad y búsqueda consistente |
| `media_type` | MIME detectado por contenido cuando sea posible |
| `extension` | Valor normalizado, útil para filtro; no determina seguridad |
| `size` | Bytes del blob para archivos; tamaño agregado no se calcula al listar |
| `blob_key` | Identificador opaco solo para archivos materializados |
| `trashed_at` | Nulo o instante de entrada a papelera |
| `revision` | Control optimista para mutaciones concurrentes |

Invariantes:

- Existe una raíz única, que no puede renombrarse, moverse ni eliminarse.
- Dos hijos activos de una carpeta no comparten `normalized_name`.
- Una carpeta no puede moverse dentro de sí misma ni de un descendiente.
- Renombrar o mover cambia metadatos, nunca la ubicación física de un blob.
- Un archivo visible referencia exactamente un blob finalizado.
- Los identificadores recibidos nunca se convierten en rutas del usuario.

El árbol usa relación de adyacencia (`parent_id`) para que mover una carpeta
sea O(1) en número de descendientes. Las consultas recursivas excepcionales
usan CTE; no se mantiene una ruta materializada que obligue a actualizar miles
de filas.

## Papelera

Mover a papelera crea un `TrashRecord` para la raíz seleccionada con su padre
original y fecha. Los descendientes quedan ocultos por pertenecer a esa raíz,
sin reescribirlos. Restaurar valida el destino y resuelve conflictos de nombre
de forma explícita. Vaciar papelera crea un job que elimina metadatos por lotes
y blobs no referenciados; no bloquea una petición HTTP larga.

## Blobs

`Blob` describe contenido físico por clave opaca, tamaño, checksum opcional,
estado (`staging`, `ready`, `deleting`) y timestamps. La primera versión no
hace deduplicación automática: evita costes de hash obligatorios sobre 50 GB y
reduce acoplamiento. El contrato deja posible añadirla después.

## Aggregate `UploadSession`

Conserva longitud declarada, offset confirmado, destino, nombre, expiración y
estado. Solo acepta escritura en el offset esperado; finalizar es idempotente.
Una sesión completada no admite bytes adicionales.

## `MediaAsset`

Representa un derivado de un blob: miniatura de imagen, fotograma de video o
miniatura de PDF. Incluye variante, MIME, dimensiones, estado y clave física.
Los derivados pueden regenerarse y no forman parte del backup esencial.

## Identidad

`AdminAccount` es un singleton lógico con hash Argon2id y estado habilitado.
`AuthSession` contiene únicamente el hash del refresh token rotatorio,
expiración y datos mínimos de revocación. No existe registro público ni CRUD de
usuarios.

## Actividad

- `Favorite` relaciona la cuenta implícita con un `EntryId` y es idempotente.
- `RecentOpen` registra última apertura y contador; no cada solicitud Range.
- Los accesos a miniaturas no alteran recientes.

## Jobs

Un `Job` durable incluye tipo, payload versionado, estado, intentos,
`available_at`, lease y error sanitizado. Los handlers son idempotentes. Se
usará para copias recursivas, vaciado de papelera, miniaturas y mantenimiento.

## Modelo relacional previsto

Tablas principales: `entries`, `blobs`, `trash_records`, `upload_sessions`,
`media_assets`, `favorites`, `recent_opens`, `admin_account`, `auth_sessions`,
`jobs` y `outbox_events`. Las migraciones e índices exactos pertenecen a la
Fase 2 y deberán verificarse con planes reales de PostgreSQL.
