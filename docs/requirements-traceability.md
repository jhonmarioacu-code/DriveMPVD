# Trazabilidad de requisitos

Esta matriz garantiza que cada requisito solicitado tiene una decisión de
arquitectura y una fase de implementación. “Diseñado” no significa implementado
en la Fase 1.

| Requisito | Decisión/contrato | Fase principal |
|---|---|---|
| Usuario único y login | Singleton `AdminAccount`, sin registro/roles | 2.3 backend y 4 frontend implementados |
| Crear, renombrar, mover, copiar y borrar | Entidades, commands, UoW y REST | 2.5 API implementada |
| Carpetas y subcarpetas | Adyacencia, CTE y listado keyset | 2.5 API implementada |
| Lista, cuadrícula, breadcrumb y menú | App shell/features virtualizadas | 3 y 5 |
| Subir archivos/carpetas y drag-and-drop | API reanudable; carpetas/UI futuras | 2.6 subida de archivo implementada |
| Archivos de hasta 50 GB | Streaming, offsets, SHA-256 y publicación atómica | 2.6 implementado |
| Descargar/abrir | Streaming RFC 9110; estrategia Nginx preparada | 2.7 implementado |
| Imágenes con zoom/rotación/fullscreen | Feature `previews` | 7 |
| Video y música | Range implementado; reproductores futuros | 2.7 backend; 7 frontend |
| PDF integrado | Visor lazy con rangos | 7 y 8 |
| Miniaturas imagen/video/PDF | `MediaAsset` + worker durable | 7 |
| Word/Excel/PowerPoint/TXT/ZIP/RAR/7Z | Clasificación MIME/extensión e iconos | 5 |
| Búsqueda por metadatos | `pg_trgm`, filtros y cursores | 5 y 9 |
| Orden nombre/fecha/tamaño/tipo | Keyset con desempate por id | 2.5 implementado |
| Favoritos y recientes | Módulo `activity` | 5 |
| Papelera/restaurar/vaciar | REST para trash/restore/purge; vaciado futuro | 2.5 parcial implementado |
| Argon2, JWT, CSRF y rate limit | Cookies HttpOnly, refresh rotatorio, PostgreSQL | 2.3 backend y 4 frontend implementados |
| Headers y validación de subida | CSRF cliente; Nginx, middleware y value objects | 4 cliente implementado; 6 y 9 |
| Protección path traversal | Blob UUID y confinamiento de raíz | 2 y 6 |
| Solo `/data/storage` | Object store local sharded | 2 |
| 500k archivos/100k carpetas | Índices, cursores, queries proyectadas | 2 y 9 |
| REST, Swagger y OpenAPI | `/api/v1`, envelope y contrato generado | 2.5 almacenamiento implementado |
| Responsive, temas y notificaciones | Shell/temas en 3.1; feedback por commands futuro | 3.1 implementado; 5–7 |
| Atajos de teclado | Commands compartidos y control de foco | 5 |
| 80 % de cobertura | Umbral de líneas/ramas y pirámide definida | 10 |
| Type hints y calidad | Type checker, Ruff/Black, ESLint/Prettier | 2 y 3.1 implementados; 10 |
| Docker Compose y Nginx | Topología de cuatro servicios | 2–4 y 9 |
| Ubuntu 24.04 | Guía y verificación de host | 9 |
| Instalar/actualizar/backup/restaurar | Procedimientos verificables previstos | 9 |
| Extensibilidad futura | Módulos y puertos, sin abstracciones especulativas | Transversal |
| DI solo en infraestructura | Composition root único y factories de rutas | 2 |
| Settings centralizado | Variables `DRIVEMPVD_*`, validación fail-fast | 2 |
| Logging JSON | Formatter estructurado y request id | 2 |
| Errores globales | Jerarquías por capa y traducción HTTP única | 2 |
| Respuesta uniforme | Envelope `data/error/meta` | 2 |
| API docs automáticas | FastAPI OpenAPI como fuente única | 2 |
| Storage intercambiable | Puerto streaming y adaptador local | 2.6 local implementado; S3/MinIO futuro |
| PostgreSQL Full Text futuro | Puerto de búsqueda y evolución `tsvector`/GIN | 5 y 9 |
| Versiones mínimas | Python 3.13, PostgreSQL 16, React 19, TypeScript 5.x | 2 y 3.1 implementados |
| Sin librerías experimentales | Solo releases estables y mantenidas | Transversal |

## Criterio de fase

Cada fase deberá actualizar esta matriz, ejecutar sus verificaciones y marcar
solo capacidades realmente operativas. No se avanzará a la fase siguiente sin
aprobación explícita del usuario.
