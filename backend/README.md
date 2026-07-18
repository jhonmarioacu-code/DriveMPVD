# Backend

El backend será un monolito modular asíncrono. La organización principal es
por capa, y dentro de cada capa se repiten los módulos de negocio definidos en
[`docs/architecture.md`](../docs/architecture.md).

```text
app/
  domain/          Reglas, entidades, value objects y eventos
  application/     Casos de uso, DTOs y puertos
  infrastructure/  Adaptadores, Settings y composition root de dependencias
  presentation/    REST, OpenAPI, middleware y traducción HTTP
  shared/          Kernel mínimo sin reglas específicas de un módulo
```

La composición e inyección de dependencias sucede exclusivamente en
`infrastructure`. Los adaptadores implementan puertos declarados por
`application`; ninguna capa interior conoce a una exterior. `presentation`
recibe casos de uso ya construidos y solo los traduce a HTTP.

## Entorno de desarrollo

Requiere Python 3.13 o posterior compatible. Las dependencias de producción y
desarrollo están fijadas con hashes en `requirements.lock` y
`requirements-dev.lock`.

```bash
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps -e .
```

Puerta de calidad del backend:

```bash
python -m black --check app tests
python -m ruff check app tests
python -m mypy app tests
python -m pytest
```

La aplicación ASGI se expone como `app.main:app`. Toda configuración disponible
está enumerada en `.env.example`; los valores reales no se versionan.
