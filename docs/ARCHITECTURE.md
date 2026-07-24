# Arquitectura de DriveMPVD

## 1. Decisión de arquitectura

DriveMPVD es un monolito modular orientado a un único administrador. API y
worker comparten artefacto, pero se ejecutan como procesos separados. Esta
decisión reduce coste operativo en una VPS única sin renunciar a límites
internos, puertos/adaptadores, transacciones locales y pruebas de dependencias.

No se extrae un servicio ni se añade broker externo sin que mediciones,
operación o un requisito concreto lo justifiquen.

## 2. Diagrama de componentes

```mermaid
flowchart TD
  Browser[Navegador]
  Nginx[Nginx]
  Frontend[SPA React/Vite]
  API[FastAPI]
  Worker[Worker de outbox]
  Migrate[Alembic migrate]
  DB[(PostgreSQL 16)]
  FS[/data/storage]

  Browser --> Nginx
  Nginx --> Frontend
  Nginx --> API
  API --> DB
  API --> FS
  Worker --> DB
  Worker --> FS
  Migrate --> DB
```

Nginx es el único borde publicado. Frontend se ubica en la red `edge`; API,
worker, migrate y PostgreSQL en `private`. API y worker son los únicos que
montan el almacenamiento persistente.

## 3. Capas backend

| Capa | Responsabilidad | Regla |
| --- | --- | --- |
| `domain` | Entidades, aggregates, value objects, eventos y reglas. | Sin frameworks ni I/O externo. |
| `application` | Casos de uso, DTOs, puertos, UoW y límites transaccionales. | Depende solo de dominio y shared. |
| `infrastructure` | PostgreSQL, storage, configuración, seguridad, logging y composition root. | Implementa puertos y hace mapping explícito. |
| `presentation` | REST, schemas, middleware, OpenAPI y traducción de excepciones. | No contiene reglas de negocio ni crea dependencias. |
| `shared` | Tipos y contratos mínimos transversales. | No es un cajón de utilidades. |

La dirección de dependencias apunta hacia el dominio. Todos los símbolos
públicos tienen type hints y MyPy corre en modo estricto.

## 4. Módulos

| Módulo | Responsabilidad |
| --- | --- |
| `catalog` | Árbol lógico, entradas, carpetas, nombres, movimientos, copias y papelera. |
| `transfers` | Sesiones de upload, offsets, finalización y descargas vía `FileStorageProvider`. |
| `media` | Contratos para MIME, thumbnails, previews y derivados; no existe worker de medios operativo. |
| `identity` | Singleton administrativo, login, sesiones, JWT, CSRF y lockout. |
| `activity` | Favoritos, recientes y actividad de apertura explícita. |
| `jobs` | Contratos de trabajo durable; el worker actual procesa outbox de storage. |

Capacidades futuras como tags, sharing, versiones, antivirus, búsqueda de
contenido y sincronización deben ser módulos nuevos. No introducir columnas
genéricas ni abstracciones anticipadas.

## 5. Decisiones consolidadas

| Decisión | Consecuencia |
| --- | --- |
| Árbol por lista de adyacencia `parent_id` | Mover/renombrar son mutaciones de metadatos; CTE para subárboles. |
| Object store local con keys UUID opacas y shards | El árbol lógico no se refleja como rutas de host; reduce traversal. |
| PostgreSQL async + SQLAlchemy 2 + UoW | Una escritura por caso de uso es atómica; ORM queda en infraestructura. |
| Outbox durable + `FOR UPDATE SKIP LOCKED` | Handlers idempotentes y entrega al menos una vez; no transportar bytes por DB. |
| JWT rotatorios en cookies + CSRF | Credenciales fuera de JavaScript, revocación inmediata y defensa replay. |
| OpenAPI de FastAPI como contrato único | No mantener una especificación REST paralela manual. |
| Keyset pagination | No `OFFSET` profundo; cursor opaco ligado a orden/dirección. |
| Streaming FastAPI hoy | `X-Accel-Redirect` está preparado, no activado. |
| Publicación de upload por staging + fsync + `os.replace` | Memoria acotada y publicación atómica dentro del mismo filesystem. |
| Outbox de huérfanos en dos fases | Se decide en DB antes de borrar bytes físicos. |

## 6. Datos y consistencia

PostgreSQL es la fuente de verdad de metadatos. `StorageObject` representa un
blob inmutable; `FileVersion` lo referencia. `Folder` y `File` se persisten
bajo una raíz lógica común. La raíz canónica no se mueve ni se elimina.

Las mutaciones usan UoW. El catálogo no conoce rutas físicas. El provider de
storage recibe claves opacas y streams asíncronos, nunca archivos completos en
memoria.

La purga emite `storage.orphan_sweep_requested`. El worker selecciona objetos
sin referencias de `FileVersion`, `Thumbnail` ni `Preview`, elimina primero
metadatos elegibles y después borra bytes idempotentemente.

## 7. Frontend

La SPA React/TypeScript se organiza por feature: `auth`, `activity`,
`explorer`, `uploads` y `viewers`. `shared/api` centraliza HTTP; los componentes
no llaman `fetch` directamente. TanStack Query administra datos remotos
paginados, no el árbol completo ni bytes de archivo.

Rutas protegidas actuales: `/home`, `/files`, `/files/:folderId`,
`/recents` y `/favorites`. El index autenticado redirige a `/home`. La
papelera no debe presentarse como flujo frontend terminado.

La composición visual incluye navegación lateral, barra superior, contenido
principal, toolbar, breadcrumb, listado/cuadrícula, diálogo de preview y bandeja
de subidas. En móvil, la navegación es drawer modal con foco atrapado/restaurado
e inert sobre fondo. Tema, lista/cuadrícula y preferencias no sensibles pueden
persistirse localmente; auth y bytes no.

La UI usa estados de carga, vacío, error y permiso explícitos. Mutaciones
optimistas se permiten solo con rollback inequívoco. Las acciones destructivas
esperan resultado del servidor. La extensión del archivo orienta iconos, no
autoriza preview ni altera la política MIME del backend.

## 8. Trazabilidad funcional

| Requisito | Estado y fuente |
| --- | --- |
| Login, JWT, CSRF, rate limit | Implementado; [SECURITY.md](SECURITY.md). |
| Árbol, carpetas, mover/copiar/papelera API | Implementado; UI de papelera incompleta. |
| Upload reanudable de archivos | Implementado; no upload de carpetas completas. |
| Download, `HEAD` y Range | Implementado; [STORAGE.md](STORAGE.md). |
| Imagen/PDF/audio/vídeo | Visores nativos/preview seguro; no transcodificación. |
| Miniaturas | Raster <= 1 MiB desde fuente; derivados servidor pendientes. |
| Favoritos y recientes | Implementados y persistentes. |
| Búsqueda global de contenido | Pendiente. |
| Offsite/retención/RPO/RTO | Pendiente. |

## 9. Procesos y límites

| Proceso | Hecho relevante |
| --- | --- |
| `nginx` | Termina TLS, añade headers, sirve SPA y proxy `/api`. |
| `frontend` | Artefactos Vite estáticos, solo red `edge`. |
| `api` | FastAPI async, auth, catálogo, uploads y streaming. |
| `worker` | Outbox de objetos huérfanos con heartbeat; no media/staging cleanup. |
| `migrate` | `alembic upgrade head` antes de API/worker. |
| `postgres` | Metadatos, sesiones, outbox y migraciones; no publica puerto. |

Para persistencia, migraciones e integridad, consulte [DATABASE.md](DATABASE.md).
Para bytes y transferencias, consulte [STORAGE.md](STORAGE.md). Para redes e
infraestructura, consulte [DOCKER.md](DOCKER.md) y [NGINX.md](NGINX.md).
