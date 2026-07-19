# DriveMPVD

DriveMPVD es un gestor personal de archivos, de un único usuario, diseñado para
desplegarse en Ubuntu Server 24.04 LTS. El proyecto usa un monolito modular con
DDD, FastAPI y PostgreSQL en el backend, y React en el frontend.

## Estado

La arquitectura, el backend hasta el incremento 2.7, la base del frontend, la
autenticación web y el explorador de archivos están terminados.

| Fase | Alcance | Estado |
|---|---|---|
| 1 | Arquitectura, límites, contratos y estructura | Terminada |
| 2 | Backend, almacenamiento y transferencias | Terminada — incrementos 2.1–2.7 |
| 3 | Frontend base | Terminada — incremento 3.1 |
| 4 | Autenticación y endurecimiento | Terminada |
| 5 | Explorador de archivos | Terminada |
| 6 | Subidas normales y reanudables | Pendiente |
| 7 | Visualizadores y miniaturas | Pendiente |
| 8 | Streaming y Range Requests | Pendiente |
| 9 | Optimización y operación | Pendiente |
| 10 | Pruebas y cobertura final | Pendiente |

## Documentación de arquitectura

- [Arquitectura y dependencias](docs/architecture.md)
- [Modelo de dominio](docs/domain-model.md)
- [Contrato y convenciones REST](docs/api.md)
- [Seguridad](docs/security.md)
- [Almacenamiento y transferencias](docs/storage.md)
- [Dominio de almacenamiento implementado](docs/storage-domain.md)
- [Rendimiento y escalabilidad](docs/performance.md)
- [Arquitectura del frontend](docs/frontend-architecture.md)
- [Estrategia de pruebas](docs/testing-strategy.md)
- [Despliegue y operación previstos](docs/operations.md)
- [Trazabilidad de requisitos](docs/requirements-traceability.md)
- [Registro de decisiones](docs/adr/README.md)

## Estructura

```text
backend/
  app/
    domain/
    application/
    infrastructure/
    presentation/
    shared/
frontend/
docs/
docker/
```

Cada directorio contiene su contrato de responsabilidad. La regla central es
que dominio y aplicación no importan FastAPI, SQLAlchemy, PostgreSQL, Nginx ni
detalles del sistema de archivos.

## Requisitos objetivo

- Python 3.13, FastAPI, SQLAlchemy 2 y Alembic.
- PostgreSQL; React, TypeScript, Vite, Tailwind CSS y shadcn/ui.
- Docker Compose y Nginx sobre Ubuntu Server 24.04 LTS.
- Datos persistentes exclusivamente bajo `/data/storage`; la base de datos
  conserva metadatos, nunca el contenido de los archivos.

Las instrucciones ejecutables de instalación, actualización, copia de
seguridad, restauración y despliegue se incorporarán cuando existan los
artefactos reales de contenedor. Su diseño ya está definido en
[`docs/operations.md`](docs/operations.md).
