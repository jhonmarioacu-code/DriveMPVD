# Dominio de almacenamiento

Este incremento modela el árbol lógico y sus metadatos. No implementa API,
subidas, streaming ni generación de derivados. El dominio no importa FastAPI,
SQLAlchemy, PostgreSQL ni adaptadores de archivos.

## Modelo

| Entidad | Responsabilidad |
|---|---|
| `Folder` | Nodo contenedor del árbol lógico. |
| `File` | Nombre visible y metadatos de la versión actual. |
| `StorageObject` | Contenido físico inmutable identificado por una clave opaca. |
| `FileVersion` | Snapshot inmutable que relaciona archivo y objeto. |
| `Thumbnail` / `Preview` | Estado de un derivado regenerable. |
| `UploadSession` | Estado futuro de una carga reanudable, sin contener bytes. |
| `TrashItem` | Tombstone de la raíz eliminada y su padre original. |

`Folder` y `File` son entidades distintas en dominio. La infraestructura usa
una tabla común `storage_entries` para poder aplicar unicidad, jerarquía y
consultas recursivas de forma uniforme; `file_metadata` contiene solo atributos
de archivo. Los modelos ORM nunca salen del repositorio.

## Jerarquía

Se eligió una lista de adyacencia mediante `parent_id`:

- listar hijos usa el índice `(parent_id, normalized_name, id)`;
- mover un nodo requiere actualizar una fila;
- detectar ciclos, copiar, enviar a papelera, restaurar y purgar usan CTE
  recursivos de PostgreSQL;
- los subárboles se procesan mediante cursor asíncrono y no se materializan
  completos en memoria.

Una ruta materializada aceleraría lecturas de ancestros, pero obligaría a
reescribir todos los descendientes en cada movimiento. Para 100 000 carpetas,
la lista de adyacencia ofrece un coste de escritura más predecible.

## Invariantes

- Hay como máximo una raíz activa por propietario; siempre es una carpeta.
- La raíz no se renombra, mueve, copia ni elimina.
- Dos hijos activos del mismo padre no comparten nombre normalizado.
- Los nombres se normalizan con NFC/NFKC y rechazan separadores, segmentos
  `.`/`..`, NUL y caracteres de control.
- Una carpeta no puede moverse dentro de sí misma o de un descendiente.
- `size` no es negativo y `checksum_sha256` es un digest hexadecimal canónico.
- Un `FileVersion` es inmutable y referencia un `StorageObject` inmutable.
- Enviar una carpeta a papelera oculta atómicamente todo el subárbol. Solo su
  raíz obtiene `TrashItem`; restaurar recupera el conjunto completo.
- Toda mutación ocurre dentro de un `UnitOfWork` y se confirma una sola vez.
- Ninguna clave de almacenamiento se interpreta como ruta suministrada por el
  usuario.

## Copia y eliminación física

Copiar un archivo crea otro `File` y otro `FileVersion`, pero ambos pueden
referenciar el mismo objeto inmutable. Es copy-on-write preparado para
versionado; no es deduplicación global. El índice no único
`(checksum_sha256, size)` permite evaluar deduplicación posteriormente sin
cambiar el dominio.

La eliminación definitiva borra metadatos del subárbol y publica
`storage.orphan_sweep_requested` en el outbox dentro de la misma transacción.
No elimina bytes directamente: un proceso futuro deberá comprobar que ningún
`FileVersion` referencia el objeto antes de pedir su borrado al proveedor.

## Puertos

- `FileStorageProvider`: lectura/escritura/rangos por streams asíncronos y
  claves opacas; habilita local, S3 o MinIO.
- `ThumbnailGenerator` y `PreviewGenerator`: producen chunks, no buffers
  completos.
- `MetadataExtractor`: extrae metadatos desde un stream.
- `VirusScanner`: inspecciona un stream y devuelve un resultado tipado.

Los puertos no tienen adaptadores en este incremento. Etiquetas, enlaces,
OCR, antivirus y sincronización podrán añadirse como módulos/casos de uso que
referencien identificadores de archivo o versión, sin cambiar estas reglas.

## Limitaciones conocidas

- La raíz canónica `Drive` se crea atómicamente al aprovisionar el administrador;
  la migración `20260718_0004` completa administradores existentes que aún no la
  tengan. No existe endpoint público de inicialización.
- El explorador usa listado keyset y la navegación HTTP de breadcrumbs. La
  búsqueda global continúa pendiente.
- La copia recursiva es transaccional y streaming, pero una carpeta enorme
  mantendría una transacción larga. Antes de habilitarla por API conviene fijar
  un umbral y delegar copias grandes a jobs idempotentes.
- El evento de barrido queda en outbox; el worker físico aún no existe.
- Las sesiones de subida y derivados se persisten para estabilizar el modelo,
  pero todavía no se ejecutan.
