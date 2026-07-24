# DriveMPVD — Documentación oficial

DriveMPVD es una nube privada personal para un único administrador. Gestiona
archivos y carpetas, transferencias reanudables, descargas con Range, actividad,
previsualización segura y operación sobre una VPS.

Esta carpeta es la fuente documental oficial del proyecto. Los informes de
auditoría solicitados para una reorganización se conservan en la raíz como
artefactos puntuales: [DOCUMENTATION_AUDIT.md](../DOCUMENTATION_AUDIT.md) y
[CLEANUP_REPORT.md](../CLEANUP_REPORT.md).

## Inicio rápido

1. Lea [AGENTS.md](AGENTS.md) antes de modificar código, configuración o
   infraestructura.
2. Revise [ARCHITECTURE.md](ARCHITECTURE.md) para comprender límites y flujos.
3. Use [DEVELOPMENT.md](DEVELOPMENT.md) para preparar y validar el entorno
   local.
4. Antes de una entrega, siga [RELEASE.md](RELEASE.md) y
   [DEPLOYMENT.md](DEPLOYMENT.md).

## Mapa documental

| Documento | Contenido |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Manual operativo para agentes de IA, desarrolladores y revisores. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Arquitectura, módulos, decisiones y límites técnicos. |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Desarrollo local, convenciones y calidad de código. |
| [API.md](API.md) | Contrato REST y reglas de compatibilidad. |
| [DATABASE.md](DATABASE.md) | PostgreSQL, modelo de datos, migraciones e integridad. |
| [STORAGE.md](STORAGE.md) | Objetos físicos, subidas, descargas, streaming y limpieza. |
| [SECURITY.md](SECURITY.md) | Autenticación, protección, secretos y hardening. |
| [TESTING.md](TESTING.md) | Estrategia, gates, comandos y evidencia de pruebas. |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Proceso reproducible de despliegue y verificación. |
| [VPS.md](VPS.md) | Preparación y validación de Ubuntu Server. |
| [DOCKER.md](DOCKER.md) | Dockerfiles, Compose, servicios, redes e imágenes. |
| [NGINX.md](NGINX.md) | Borde HTTP/HTTPS, TLS, headers y proxy. |
| [BACKUP.md](BACKUP.md) | Copias, restore drill, recuperación y rollback. |
| [OPERATIONS.md](OPERATIONS.md) | Operación cotidiana, mantenimiento, observabilidad e incidentes. |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Diagnóstico de fallos conocidos y acciones seguras. |
| [CHANGELOG.md](CHANGELOG.md) | Historial consolidado de cambios relevantes. |
| [RELEASE.md](RELEASE.md) | Trazabilidad Git, sincronización, RC y producción pública. |

## Estado de referencia

La última evidencia consolidada describe una candidata privada en Ubuntu 24.04
con PostgreSQL, API, worker, frontend y Nginx sanos. No equivale a una
publicación pública: faltan dominio/DNS, TLS público validado, trazabilidad Git
remota, pruebas de Internet/concurrencia/50 GiB y una política de backup
offsite. Consulte [RELEASE.md](RELEASE.md) antes de declarar producción.

## Principios

- Un único administrador; no hay registro público, multi-tenencia, roles ni ACL.
- PostgreSQL es la fuente de verdad de metadatos; los bytes viven bajo
  `/data/storage`.
- Los archivos y secretos no se guardan en Git, imágenes ni checkout.
- Una build exitosa no certifica seguridad, recuperabilidad ni producción.
- Toda afirmación operativa requiere evidencia fechada y reproducible.
