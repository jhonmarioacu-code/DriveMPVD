# API FastAPI

## 1. Convenciones

- Prefijo actual: `/api/v1`.
- OpenAPI generado por FastAPI es la especificación ejecutable y única.
- `/openapi.json`, `/docs` y `/redoc` derivan de ese contrato cuando estén
  habilitados por entorno.
- Las respuestas JSON usan un envelope `data/error/meta`; streams y respuestas
  sin cuerpo son excepciones deliberadas.
- Cambios aditivos conservan versión; incompatibilidades requieren una versión
  nueva, por ejemplo `/api/v2`.
- Las mutaciones autenticadas por cookie requieren `X-CSRF-Token`.

No mantenga una copia JSON estática o documentación paralela de schemas.

## 2. Recursos disponibles

| Área | Rutas principales |
| --- | --- |
| Sistema | `GET /api/v1/health`, `GET /api/v1/ready`. |
| Auth | Login, sesión, refresh, logout, cambio de contraseña y revocación según OpenAPI. |
| Navegación | `GET /api/v1/storage/navigation`. |
| Catálogo | Listar hijos, metadatos de archivo, crear carpeta, renombrar, mover, copiar y papelera. |
| Uploads | Crear sesión, `HEAD` offset, `PATCH` chunk, completar y cancelar. |
| Contenido | `GET/HEAD /api/v1/storage/files/{file_id}/content`. |
| Actividad | Favoritos y recientes bajo `/api/v1/activity`. |

### Catálogo

| Método | Ruta | Acción |
| --- | --- | --- |
| `GET` | `/storage/folders/{folder_id}/entries` | Hijos directos paginados. |
| `GET` | `/storage/files/{file_id}` | Metadatos de archivo. |
| `POST` | `/storage/folders` | Crear carpeta. |
| `PATCH` | `/storage/entries/{entry_id}` | Renombrar. |
| `POST` | `/storage/entries/{entry_id}/move` | Mover. |
| `POST` | `/storage/entries/{entry_id}/copy` | Copiar. |
| `POST` | `/storage/entries/{entry_id}/trash` | Enviar a papelera. |
| `POST` | `/storage/trash/{trash_item_id}/restore` | Restaurar subárbol. |
| `DELETE` | `/storage/trash/{trash_item_id}` | Purga definitiva de metadatos. |

Los listados aceptan cursor, límite, orden y filtros descritos por OpenAPI. El
límite de página es 200. Usan keyset con cursor opaco; no introducir `OFFSET`
profundo.

## 3. Autenticación

La SPA usa `delivery=cookie`. Access, refresh y CSRF siguen el modelo de
[SECURITY.md](SECURITY.md). Las rutas de lectura pueden usar cookie o Bearer
cuando el contrato lo admite; Bearer tiene precedencia si se envía junto con
cookie.

Una respuesta 401 debe permitir una única renovación serializada en cliente.
Una mutación sin CSRF debe fallar con 403; no relajar esa protección para
resolver un problema de cliente.

| Método | Ruta | Acción |
| --- | --- | --- |
| `POST` | `/auth/login` | Autentica al administrador. |
| `POST` | `/auth/refresh` | Rota refresh y emite credenciales. |
| `POST` | `/auth/logout` | Revoca la sesión actual y borra cookies. |
| `POST` | `/auth/sessions/revoke-all` | Revoca todas las sesiones del administrador. |
| `GET` | `/auth/session` | Devuelve identidad de sesión autenticada. |

## 4. Upload reanudable

| Método | Ruta | Semántica |
| --- | --- | --- |
| `POST` | `/storage/uploads` | Crea sesión con parent, nombre, tamaño y MIME declarado. |
| `HEAD` | `/storage/uploads/{upload_id}` | Devuelve offset, longitud, estado y expiración. |
| `PATCH` | `/storage/uploads/{upload_id}` | Recibe `application/offset+octet-stream` con `Upload-Offset`. |
| `POST` | `/storage/uploads/{upload_id}/complete` | Verifica y publica. |
| `DELETE` | `/storage/uploads/{upload_id}` | Cancela y limpia staging controlado. |

El servidor es autoridad de offset, límites, autorización, MIME, checksum y
publicación. Un 409 de offset se reconcilia con `HEAD`; el cliente no adivina
ni salta bytes. Consulte [STORAGE.md](STORAGE.md).

## 5. Actividad

| Método | Ruta | Acción |
| --- | --- | --- |
| `GET` | `/activity/favorites` | Lista favoritos activos con keyset. |
| `PUT` | `/activity/favorites/{entry_id}` | Marca una entrada activa como favorita. |
| `DELETE` | `/activity/favorites/{entry_id}` | Quita un favorito. |
| `GET` | `/activity/recents` | Lista aperturas recientes activas. |
| `POST` | `/activity/recents/{entry_id}` | Registra una apertura explícita de usuario. |

El streaming, `HEAD` o Range de contenido no registran recientes. Las
mutaciones requieren la misma auth/CSRF que el resto de API.

## 6. Descargas y preview

`GET/HEAD /storage/files/{file_id}/content` conserva autorización, ETag,
`Last-Modified`, precondiciones y Range RFC 9110. El default es
`Content-Disposition: attachment`. El query `disposition=inline` solo se
honra para MIME seguros: PDF, imagen raster, audio o vídeo definidos por el
backend. HTML, SVG y tipos activos permanecen como adjunto.

Se admiten rangos únicos, abiertos, sufijos y multipart limitado. `HEAD` y
`GET` comparten autorización y cabeceras. Una falla física después de iniciar
un stream solo puede cerrar conexión; no se puede convertir en envelope JSON.

## 7. Compatibilidad

Antes de cambiar una ruta, schema, código de error, cursor, header o cookie:

1. comprobar consumidores frontend y smoke;
2. añadir o actualizar prueba de contrato;
3. preservar compatibilidad o versionar;
4. actualizar OpenAPI y este documento;
5. repetir validación de auth/CSRF/Range si corresponde.

El detalle de modelos y permisos pertenece a [DATABASE.md](DATABASE.md); los
flujos de bytes a [STORAGE.md](STORAGE.md).
