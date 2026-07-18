# ADR-0007: PostgreSQL asíncrono, UoW y outbox

- Estado: aceptada
- Fecha: 2026-07-18

## Contexto

La persistencia debe soportar transacciones atómicas, alto volumen, paginación
y eventos durables sin contaminar el dominio con SQLAlchemy.

## Decisión

Usar PostgreSQL 16 con SQLAlchemy 2 asíncrono/asyncpg. Cada caso de uso de
escritura abrirá un `UnitOfWork`, cuyos repositorios comparten una única
`AsyncSession` y nunca hacen commit. Los puertos viven en aplicación y los
modelos ORM/mappers exclusivamente en infraestructura.

La primera tabla real es `outbox_events`: permite que futuros cambios de
aggregate y sus eventos se confirmen en la misma transacción. Sus ids se generan
en aplicación mediante un puerto implementado por un generador UUID v7
monotónico; PostgreSQL impide almacenar otra versión de UUID.

## Consecuencias

Las escrituras de un caso de uso son atómicas y los tests usan PostgreSQL real,
no SQLite. Los listados usan keyset `(created_at, id)` y límite máximo. Cada
repositorio debe mapear explícitamente ORM ↔ dominio/DTO y declarar estrategias
de carga; las relaciones futuras usarán `lazy="raise"` y `selectinload` o
`joinedload` explícito para impedir N+1.

La outbox aún no tiene worker de publicación, leases ni política de retención;
eso corresponde al módulo de jobs. Hasta entonces solo proporciona la frontera
transaccional durable.
