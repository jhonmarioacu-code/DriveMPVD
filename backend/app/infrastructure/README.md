# Infrastructure

Implementa los puertos de aplicación con SQLAlchemy 2/Alembic, PostgreSQL,
almacenamiento bajo `/data/storage`, Argon2id, JWT, generación de miniaturas,
FFmpeg y trabajos persistentes.

Los modelos ORM se mantienen separados de las entidades de dominio y se
convierten explícitamente en los repositorios.

También contiene el único composition root: carga el objeto `Settings` central
desde variables de entorno, crea adaptadores y los inyecta por constructor en
los casos de uso antes de entregarlos a `presentation`.
