# ADR-0009: Adyacencia y objetos inmutables para almacenamiento

- Estado: aceptado
- Fecha: 2026-07-18

## Contexto

El sistema debe manejar cientos de miles de entradas, movimientos baratos,
archivos de hasta 50 GB y proveedores físicos intercambiables. Las entidades
de dominio no pueden depender del esquema relacional ni del filesystem.

## Decisión

Usar una tabla lógica común para nodos, jerarquía por `parent_id`, metadatos de
archivo separados y contenido físico representado por `StorageObject`
inmutable. Cada versión referencia un objeto. Las operaciones recursivas usan
CTE y el repositorio traduce explícitamente modelos ORM a entidades.

La papelera aplica soft delete a todo el subárbol en una sentencia y conserva
un único `TrashItem` para la raíz. La purga emite un evento outbox para el
barrido posterior de objetos sin referencias.

## Consecuencias

- Mover es O(1) respecto al número de descendientes.
- Listar hijos tiene un índice directo y no requiere joins recursivos.
- Copiar archivos comparte contenido de forma segura sin activar deduplicación.
- Obtener rutas completas y operar subárboles requiere CTE recursivo.
- Las copias recursivas muy grandes deberán migrar a jobs antes de exponerse.
- Local, S3 y MinIO permanecen fuera del dominio tras `FileStorageProvider`.
