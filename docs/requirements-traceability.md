# Trazabilidad de requisitos

Esta matriz garantiza que cada requisito solicitado tiene una decisión de
arquitectura y una fase de implementación. “Diseñado” no significa implementado
en la Fase 1.

| Requisito                                | Decisión/contrato                                                                   | Fase principal                                               |
| ---------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| Usuario único y login                    | Singleton `AdminAccount`, sin registro/roles                                        | 2.3 backend y 4 frontend implementados                       |
| Crear, renombrar, mover, copiar y borrar | Entidades, commands, UoW y REST                                                     | 2.5 API implementada                                         |
| Carpetas y subcarpetas                   | Adyacencia, CTE, raíz canónica y listado keyset                                     | 2.5 backend y 5 frontend implementados                       |
| Lista, cuadrícula, breadcrumb y menú     | App shell, TanStack Query y explorer responsive                                     | 3 y 5 implementados                                          |
| Subir archivos y drag-and-drop           | API reanudable; selección múltiple, cola y chunks; carpetas pendientes de contrato  | 2.6 backend y 6 frontend implementados                       |
| Archivos de hasta 50 GB                  | Streaming, offsets, SHA-256, publicación atómica y benchmark seguro                 | 2.6/6 implementados; 9 local validado, host 50 GiB pendiente |
| Descargar/abrir                          | Streaming RFC 9110; `attachment` por defecto e `inline` restringido a MIME seguros  | 2.7 backend y 7 frontend implementados                       |
| Imágenes con zoom/rotación/fullscreen    | Visor nativo de imagen con zoom y rotación; fullscreen queda diferido               | 7 implementado                                               |
| Video y música                           | Range RFC 9110 y reproductores HTML5 nativos                                        | 2.7 backend y 7 frontend implementados                       |
| PDF integrado                            | Visor PDF nativo del navegador sobre entrega `inline` y rangos                      | 7 implementado; PDF.js/worker no requerido en esta fase      |
| Miniaturas imagen/video/PDF              | Fuente raster <= 1 MiB perezosa y placeholders; derivados durables quedan diferidos | 7 implementado                                               |
| Word/Excel/PowerPoint/TXT/ZIP/RAR/7Z     | Clasificación MIME/extensión e iconos                                               | 5 implementado                                               |
| Búsqueda por metadatos                   | `pg_trgm`, filtros y cursores                                                       | 5 y 9                                                        |
| Orden nombre/fecha/tamaño/tipo           | Keyset con desempate por id y controles de explorer                                 | 2.5 y 5 implementados                                        |
| Favoritos y recientes                    | Módulo `activity`                                                                   | 5                                                            |
| Papelera/restaurar/vaciar                | REST para trash/restore/purge; vaciado futuro                                       | 2.5 parcial implementado                                     |
| Argon2, JWT, CSRF y rate limit           | Cookies HttpOnly, refresh rotatorio, PostgreSQL                                     | 2.3 backend y 4 frontend implementados                       |
| Headers y validación de subida           | CSRF cliente; Nginx, middleware y value objects                                     | 2.6 backend, 4/6 frontend y 8 despliegue implementados       |
| Protección path traversal                | Blob UUID y confinamiento de raíz; el cliente no construye rutas                    | 2.6 backend y 6 frontend implementados                       |
| Solo `/data/storage`                     | Object store local sharded                                                          | 2                                                            |
| 500k archivos/100k carpetas              | Índices, cursores, queries proyectadas y `EXPLAIN` de escala                        | 2 implementado; 9 plan de host pendiente                     |
| REST, Swagger y OpenAPI                  | `/api/v1`, envelope y contrato generado                                             | 2.5 almacenamiento implementado                              |
| Responsive, temas y notificaciones       | Shell/temas, explorer responsive, bandeja de subida y diálogo de visor              | 3.1, 5, 6 y 7 implementados                                  |
| Atajos de teclado                        | Commands compartidos y control de foco                                              | 5                                                            |
| 80 % de cobertura                        | Umbral de líneas/ramas y pirámide definida                                          | 10                                                           |
| Type hints y calidad                     | Type checker, Ruff/Black, ESLint/Prettier                                           | 2 y 3.1 implementados; 10                                    |
| Docker Compose y Nginx                   | Cinco servicios, dos redes, TLS y proxy de transferencias                           | 8 implementado; prueba runtime de host pendiente             |
| Ubuntu 24.04                             | Guía de host, certificados y variables                                              | 8 implementado; verificación de host pendiente               |
| Instalar/actualizar/backup/restaurar     | Procedimientos operativos y smoke test autenticado                                  | 8 implementado; restauración ensayada pendiente              |
| Extensibilidad futura                    | Módulos y puertos, sin abstracciones especulativas                                  | Transversal                                                  |
| DI solo en infraestructura               | Composition root único y factories de rutas                                         | 2                                                            |
| Settings centralizado                    | Variables `DRIVEMPVD_*`, validación fail-fast                                       | 2                                                            |
| Logging JSON                             | Formatter estructurado y request id                                                 | 2                                                            |
| Errores globales                         | Jerarquías por capa y traducción HTTP única                                         | 2                                                            |
| Respuesta uniforme                       | Envelope `data/error/meta`                                                          | 2                                                            |
| API docs automáticas                     | FastAPI OpenAPI como fuente única                                                   | 2                                                            |
| Storage intercambiable                   | Puerto streaming y adaptador local                                                  | 2.6 local implementado; S3/MinIO futuro                      |
| PostgreSQL Full Text futuro              | Puerto de búsqueda y evolución `tsvector`/GIN                                       | 5 y 9                                                        |
| Versiones mínimas                        | Python 3.13, PostgreSQL 16, React 19, TypeScript 5.x                                | 2 y 3.1 implementados                                        |
| Sin librerías experimentales             | Solo releases estables y mantenidas                                                 | Transversal                                                  |

## Criterio de fase

Cada fase deberá actualizar esta matriz, ejecutar sus verificaciones y marcar
solo capacidades realmente operativas. No se avanzará a la fase siguiente sin
aprobación explícita del usuario.
