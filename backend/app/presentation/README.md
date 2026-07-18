# Presentation

Expone `/api/v1`, Swagger/OpenAPI, middleware, validación de entrada y el
formato uniforme de respuestas. Traduce excepciones de dominio, aplicación e
infraestructura a errores públicos estables sin filtrar detalles internos.

No contiene reglas de negocio ni accede directamente a SQLAlchemy o al disco.
Tampoco crea dependencias: sus factories reciben casos de uso ya construidos
por el composition root de `infrastructure`.
