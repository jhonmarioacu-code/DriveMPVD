# ADR-0002: Árbol lógico y object store local

- Estado: aceptada
- Fecha: 2026-07-18

## Contexto

Los nombres y carpetas cambian con frecuencia, los archivos alcanzan 50 GB y
todo contenido debe quedar dentro de `/data/storage`.

## Decisión

Representar carpetas y nombres en PostgreSQL mediante adyacencia. Guardar blobs
inmutables con claves UUID opacas y shard en el filesystem. No reflejar el árbol
visible como rutas físicas.

## Consecuencias

Mover y renombrar son mutaciones pequeñas de metadatos; se reduce drásticamente
el riesgo de traversal. La consistencia DB/filesystem exige publicación atómica,
jobs de borrado y reconciliación de huérfanos.
