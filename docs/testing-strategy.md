# Estrategia de pruebas

El mínimo contractual global es **80 %** de líneas y ramas. Desde el incremento
2.2 el backend aplica una puerta más estricta del **90 %**. El umbral no
sustituye pruebas de invariantes, integración y flujos críticos.

Cada funcionalidad se entrega junto con sus pruebas unitarias en el mismo
incremento. Ningún módulo se considera terminado si sus pruebas, lint, formato
y tipado no pasan antes de iniciar el siguiente.

## Pirámide

- Dominio: pruebas unitarias rápidas para cada invariante y transición.
- Aplicación: casos de uso con puertos fake controlados, incluyendo rollback.
- Infraestructura: repositorios contra PostgreSQL real, migraciones hacia
  adelante y atrás, filesystem temporal y adaptadores de medios.
- API: contratos HTTP, autenticación, CSRF, Problem Details y OpenAPI.
- Frontend: componentes y features con servidor simulado a partir del contrato.
- E2E: navegador real para login, navegación, drag-and-drop, subida reanudada,
  papelera, preview y Range.
- No funcionales: carga, seguridad, backup/restore y fallos durante publicación.

PostgreSQL no se reemplaza por SQLite en integración: sus constraints,
collations, locks, extensiones e índices son parte del producto.

## Casos obligatorios

- Path traversal con variantes Unicode, separadores y rutas de carpetas.
- Conflictos y ciclos al mover, restaurar y copiar.
- Repetición idempotente y fallos entre blob y commit.
- Chunks fuera de orden, truncados, repetidos, excedidos y reanudados.
- Rangos válidos, múltiples, no satisfacibles y condicionales.
- Entrega `inline` solo para MIME seguros, preflight `HEAD`, visores nativos y
  fallbacks de descarga ante tipo no compatible o error multimedia.
- Umbral de miniatura: imagen raster pequeña perezosa, y placeholder para
  vídeo, PDF, tamaño desconocido o blob grande.
- Tokens expirados/revocados, rotación, reutilización de refresh y CSRF ausente.
- Paginación sin duplicados/omisiones bajo orden estable.
- Archivos maliciosos o corruptos para imagen, video y PDF.
- Operaciones con árboles grandes sin crecimiento no acotado de memoria.

## Puertas de calidad

Backend desde el primer incremento: Ruff, Black en modo check, MyPy estricto,
Pytest y cobertura. Frontend desde su bootstrap: ESLint, Prettier en modo check,
`tsc --noEmit`, tests y build Vite.
Contenedores: escaneo de dependencias/imágenes, healthchecks y smoke test de
Compose. CI falla si OpenAPI cambió sin regenerar/verificar el cliente.
