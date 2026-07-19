# Rendimiento

## Objetivos de diseño

- 500 000 archivos y 100 000 carpetas.
- Archivos individuales de hasta 50 GB.
- Listados interactivos y búsqueda por metadatos sin cargar colecciones completas.
- Streaming con uso de memoria independiente del tamaño del archivo.

No se prometen latencias hasta medir el hardware y el dataset reales. La Fase 9
establecerá presupuestos, pruebas de carga y resultados reproducibles.

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
sintéticos de escala objetivo antes de fijarlos en migraciones.

## API y memoria

- Límite máximo de 200 elementos por página.
- Streaming de request/response; sin `read()` completo de archivos.
- Pools de conexiones acotados y timeouts en DB, HTTP y procesamiento.
- Cancelación propagada cuando el navegador abandona una operación.
- Copias recursivas y vaciado por lotes en worker, con progreso y reintentos.

## Frontend

- Virtualización en listas/cuadrículas extensas.
- Debounce y cancelación de búsquedas; cache por cursor y carpeta.
- Subidas con concurrencia limitada, reanudación y progreso por bytes.
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

## Validación prevista

La suite de rendimiento generará al menos 600 000 entries, medirá p50/p95/p99
de navegación y búsqueda, subirá un archivo disperso de 50 GB donde el entorno
lo permita, verificará memoria constante y probará múltiples Range Requests.
