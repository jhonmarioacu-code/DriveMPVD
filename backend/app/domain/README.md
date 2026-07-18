# Domain

Contiene entidades, aggregates, value objects, servicios de dominio, eventos y
errores propios de `catalog`, `transfers`, `media`, `identity` y `activity`.

No puede importar FastAPI, Pydantic, SQLAlchemy, librerías de JWT, drivers de
PostgreSQL, acceso al disco ni objetos HTTP. Sus pruebas deben poder ejecutarse
sin base de datos y sin sistema de archivos.
