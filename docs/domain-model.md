# Modelo de dominio

El módulo de almacenamiento está implementado y se detalla en
[Dominio de almacenamiento](storage-domain.md). Los módulos posteriores de
actividad y jobs continúan como diseño previsto.

## Entidades `Folder` y `File`

Representan carpetas y archivos distintos en dominio. La infraestructura los
persiste bajo una raíz lógica común.

| Concepto          | Regla                                                                  |
| ----------------- | ---------------------------------------------------------------------- |
| `id`              | UUID v7 generado por la aplicación, inmutable                          |
| `parent_id`       | Carpeta padre; nulo solo para la raíz canónica                         |
| `entry_type`      | `file` o `folder`, nunca inferido de la extensión                      |
| `name`            | Nombre visible validado; no contiene separadores ni segmentos `.`/`..` |
| `normalized_name` | Forma normalizada para unicidad y búsqueda consistente                 |
| `mime_type`       | MIME declarado/detectado; la extracción se implementará después        |
| `extension`       | Valor normalizado, útil para filtro; no determina seguridad            |
| `size`            | Bytes del blob para archivos; tamaño agregado no se calcula al listar  |
| `checksum_sha256` | Digest canónico calculado durante la subida futura                     |
| `deleted_at`      | Nulo o instante de entrada del subárbol a papelera                     |

Invariantes:

- Existe una raíz única, que no puede renombrarse, moverse ni eliminarse.
- Dos hijos activos de una carpeta no comparten `normalized_name`.
- Una carpeta no puede moverse dentro de sí misma ni de un descendiente.
- Renombrar o mover cambia metadatos, nunca la ubicación física de un blob.
- Una versión de archivo referencia exactamente un objeto de almacenamiento.
- Los identificadores recibidos nunca se convierten en rutas del usuario.

El árbol usa relación de adyacencia (`parent_id`) para que mover una carpeta
sea O(1) en número de descendientes. Las consultas recursivas excepcionales
usan CTE; no se mantiene una ruta materializada que obligue a actualizar miles
de filas.

## Papelera

Mover a papelera crea un `TrashItem` para la raíz seleccionada y marca el
subárbol completo mediante un CTE en una sola transacción. Restaurar valida el
destino, resuelve conflictos y recupera el subárbol. La purga borra metadatos y
emite un evento outbox; la eliminación física se implementará como job.

## Objetos y versiones

`StorageObject` describe contenido físico inmutable por clave opaca, tamaño,
MIME, SHA-256 obligatorio, estado y timestamps. `FileVersion` conserva el
snapshot de metadatos y referencia el objeto. No existe deduplicación global;
una copia explícita sí puede compartir el mismo objeto inmutable.

## Aggregate `UploadSession`

Conserva longitud declarada, offset confirmado, destino, nombre, expiración y
estado. Solo acepta escritura en el offset esperado; finalizar es idempotente.
Una sesión completada no admite bytes adicionales.

## Derivados

`Thumbnail` y `Preview` representan derivados de una versión. Incluyen
variante, estado y referencia opcional a un `StorageObject`; pueden regenerarse
y no forman parte del backup esencial.

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

## Modelo relacional actual

La migración `20260718_0003` contiene `storage_entries`, `file_metadata`,
`storage_objects`, `file_versions`, `thumbnails`, `previews`,
`upload_sessions` y `trash_items`. Favoritos, recientes y jobs se incorporarán
en sus incrementos correspondientes.
