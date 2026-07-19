# Rendimiento

## Objetivos de diseño

- 500 000 archivos y 100 000 carpetas.
- Archivos individuales de hasta 50 GB.
- Listados interactivos y búsqueda por metadatos sin cargar colecciones completas.
- Streaming con uso de memoria independiente del tamaño del archivo.

No se prometen latencias universales: dependen del disco, red, CPU y dataset del
host. La Fase 9 aporta una línea base local y arneses reproducibles; los
presupuestos definitivos se fijan después de ejecutarlos en Ubuntu con
PostgreSQL y Nginx reales.

## Estrategia PostgreSQL

- Índice compuesto para hijos activos por `(parent_id, normalized_name, id)`.
- Índices parciales para papelera, favoritos, recientes y jobs disponibles.
- Índices por orden estable: fecha, tamaño, tipo/extensión más `id`.
- `pg_trgm` sobre nombre normalizado para búsqueda instantánea parcial; prefijos
  aprovechan índices B-tree cuando corresponda.
- El puerto de búsqueda y sus DTOs separan query de persistencia. La primera
  implementación usa metadatos/trigramas y puede incorporar PostgreSQL Full
  Text Search con `tsvector`/GIN sin cambiar casos de uso ni contrato HTTP.
- Keyset pagination; no se usa `OFFSET` profundo.
- Proyecciones seleccionan solo columnas visibles; blobs y payloads no entran
  en listados.
- Estadísticas, autovacuum y bloat se observan con umbrales definidos.

Los índices exactos se validarán con `EXPLAIN (ANALYZE, BUFFERS)` sobre datos
sintéticos de escala objetivo antes de fijarlos en migraciones. No se añadieron
índices especulativos durante la Fase 9: el listado usa keyset y ya dispone del
índice parcial por carpeta/nombre; los órdenes por fecha, tipo y tamaño deben
medirse con el plan real antes de aumentar el coste de escritura.

## API y memoria

- Límite máximo de 200 elementos por página.
- Streaming de request/response; sin `read()` completo de archivos.
- Los fragmentos ASGI pequeños se coalescen antes de escribir, hasta un buffer
  configurable de 1 MiB. Cada payload sigue escribiéndose y haciendo `fsync`
  sin acumular el archivo completo; además se repiten escrituras parciales si el
  filesystem no acepta todos los bytes de una vez.
- Pools de conexiones acotados y timeouts en DB, HTTP y procesamiento.
- Cancelación propagada cuando el navegador abandona una operación.
- Copias recursivas y vaciado por lotes en worker, con progreso y reintentos.

## Frontend

- Paginación keyset con `useInfiniteQuery`; la virtualización de muchas páginas
  ya cargadas sigue pendiente y debe activarse sólo tras medir un caso real de
  renderizado masivo.
- Debounce y cancelación de búsquedas; cache por cursor y carpeta.
- Subidas con concurrencia limitada, reanudación y progreso por bytes.
- Los eventos de progreso de XHR se coalescen a un máximo de una actualización
  React por cada 100 ms, conservando el último offset y evitando renders por
  cada fragmento de red.
- Miniaturas perezosas y acotadas: solo imágenes raster de hasta 1 MiB intentan
  cargar su fuente; blobs grandes nunca entran en estado global para producir
  una miniatura.
- Reproductores nativos HTML5 y visor PDF nativo bajo demanda, sobre el mismo
  endpoint autenticado con Range; no hay copia de streams en memoria React.

## Servidor objetivo

En 4 vCPU/16 GB se comienza con un proceso API asíncrono; el worker de medios
se añadirá cuando exista un ejecutor real y sus FFmpeg/renderizadores se
limitarán por semáforo. Nginx ya reenvía contenido sin buffering, mientras que
FastAPI conserva la entrega autorizada hasta habilitar un adaptador
`X-Accel-Redirect`. PostgreSQL recibe memoria reservada y no compite sin límites
con procesos multimedia.

## Línea base medida

En Windows local, Python 3.14, disco temporal local y una carga de 256 MiB con
fragmentos de entrada de 64 KiB, la mediana de dos ejecuciones pasó de
198,18 MiB/s con escrituras de 64 KiB a 248,04 MiB/s con coalescencia de 1 MiB
(+25,2 %). El pico de `tracemalloc` aumentó de aproximadamente 2,0 MiB a 3,1
MiB y se mantuvo independiente del tamaño total. La lectura en bloques de 1
MiB quedó entre 767 y 830 MiB/s en esa máquina. Son cifras de línea base, no
un SLO de producción.

La herramienta [`backend/scripts/benchmark_storage.py`](../backend/scripts/benchmark_storage.py)
repite la medición en un directorio temporal y exige `--allow-large` para una
prueba superior a 1 GiB. Para un archivo de 50 GiB en el volumen de producción:

```bash
python backend/scripts/benchmark_storage.py \
  --directory /data/bench --size-gib 50 --allow-large
```

La herramienta borra su fixture al terminar y exige espacio libre para el
archivo más una reserva. Para medir el trayecto completo autenticado contra
Compose, use [`backend/scripts/benchmark_deployment.py`](../backend/scripts/benchmark_deployment.py)
con un payload preexistente; mide p50/p95/p99 de chunks, throughput de subida y
descarga, checksum, Range de 1 MiB y el pico trazado de memoria. El resultado
debe compararse bajo 1, 2 y más procesos cliente para decidir la concurrencia
del host.

## Decisión sobre X-Accel-Redirect

Se mantiene desactivado. La entrega actual de FastAPI es acotada en memoria,
preserva autorización, `HEAD`, ETag y RFC 9110, y Nginx no aplica buffering ni
caché temporal. El overlay y ubicación `internal` ya existen, pero el proveedor
de descarga sigue devolviendo `None`; activarlo sin un adaptador y sin una
comparación real de 50 GiB podría romper autorizaciones o rangos. La decisión
se revisará tras ejecutar los benchmarks de Compose con ambos modos.
