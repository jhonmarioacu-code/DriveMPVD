# ADR-0010: Read model HTTP y paginación keyset

- Estado: aceptado
- Fecha: 2026-07-18

## Contexto

La API de almacenamiento debe exponer comandos DDD sin trasladar reglas a
FastAPI y listar hasta cientos de miles de entradas sin offsets crecientes. Los
modelos de dominio, ORM y HTTP deben permanecer separados. Las lecturas de
metadatos deben aprovechar cachés privadas sin cachear contenido binario.

## Decisión

- Los comandos reciben DTOs y devuelven DTOs de aplicación; Pydantic solo vive
  en presentación.
- Las consultas usan un read model DTO y un repositorio proyectado sobre las
  tablas existentes.
- Los listados aplican keyset compuesto por valor de orden e UUID v7. El cursor
  opaco y versionado queda ligado a campo y dirección; cambiar cualquiera lo
  invalida.
- Se admiten nombre, clase, extensión, tamaño y fecha como filtros combinables.
- `ETag` y `Last-Modified` se calculan en el adaptador HTTP, que implementa
  `If-None-Match` y `If-Modified-Since` con respuestas `304`.
- OpenAPI generado por FastAPI es la única especificación operativa.

## Consecuencias

- El coste de avanzar páginas no crece con la posición del resultado.
- Los controladores no conocen entidades ni modelos SQLAlchemy.
- El cursor no necesita firma: no concede autoridad, se valida estructuralmente
  y toda consulta vuelve a restringirse al propietario autenticado.
- Un cambio de nombre/fecha entre páginas puede mover una entrada, propiedad
  inherente a listados vivos; no se ofrece snapshot transaccional prolongado.
- Los ETag son privados y de revalidación obligatoria; no sustituyen futuras
  precondiciones de escritura con `If-Match`.
