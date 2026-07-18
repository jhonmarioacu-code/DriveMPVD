# Contrato REST

## Convenciones

- Base: `/api/v1`.
- JSON en UTF-8; fechas RFC 3339 UTC; tamaños en bytes; ids UUID.
- Toda respuesta JSON usa el mismo envelope: `data`, `error` y `meta`.
- `error` incluye `code`, `message` y errores de campo opcionales; los detalles
  internos nunca salen de la API.
- `X-Request-ID` aceptado o generado y devuelto.
- Commands mutables admiten `Idempotency-Key` donde una repetición pueda crear
  recursos o jobs.
- ETags y precondiciones evitan sobrescrituras silenciosas al renombrar/mover.
- OpenAPI es el contrato fuente para generar tipos del cliente TypeScript.

## Envelope uniforme

Una respuesta exitosa contiene `data`, `error: null` y `meta` con al menos
`request_id`; un listado añade cursores a `meta`. Una respuesta fallida contiene
`data: null`, un error tipado y el mismo `meta`. Respuestas sin body exigidas por
HTTP y streams binarios son las únicas excepciones: mantienen cabeceras y
códigos documentados en OpenAPI.

Excepciones de dominio, aplicación e infraestructura se convierten en el borde
mediante una tabla explícita de códigos y estados HTTP. Errores inesperados
responden con un código público genérico y se registran en JSON con stack trace
y `request_id`.

## Recursos previstos

| Área | Rutas principales |
|---|---|
| Sesión | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/sessions/revoke-all`, `GET /auth/session` |
| Navegación | `GET /entries`, `GET /entries/{id}`, `GET /entries/{id}/breadcrumbs` |
| Carpetas | `POST /folders` |
| Mutaciones | `PATCH /entries/{id}`, `POST /entries/{id}/move`, `POST /entries/{id}/copy`, `DELETE /entries/{id}` |
| Descarga | `GET /entries/{id}/content` |
| Subidas | `POST /uploads`, `HEAD /uploads/{id}`, `PATCH /uploads/{id}`, `POST /uploads/{id}/complete`, `DELETE /uploads/{id}` |
| Búsqueda | `GET /search` |
| Actividad | `GET /recents`, `PUT /favorites/{id}`, `DELETE /favorites/{id}`, `GET /favorites` |
| Papelera | `GET /trash`, `POST /trash/{id}/restore`, `DELETE /trash/{id}`, `DELETE /trash` |
| Medios | `GET /entries/{id}/thumbnail`, `GET /entries/{id}/preview`, `GET /jobs/{id}` |

La especificación OpenAPI concreta y validada se genera desde FastAPI a medida
que se implementan los casos de uso. Swagger UI y ReDoc consumen ese documento;
no habrá documentación manual de endpoints que pueda divergir. Este archivo
solo fija convenciones arquitectónicas, no duplica schemas operativos.

## Listados y cursores

Todos los listados requieren `limit` (por defecto 50, máximo 200) y devuelven
`items` más `next_cursor`. No existe endpoint que entregue el árbol completo.

Los cursores son opacos, firmados y contienen el último valor de orden y el id
de desempate. Orden soportado: `name`, `updated_at`, `size` y `type`, ascendente
o descendente. Cada orden añade siempre `id` como desempate estable.

La navegación filtra por `parent_id`; la búsqueda acepta nombre, extensión,
tipo, intervalos de fecha y tamaño. Las consultas vacías o excesivamente
amplias se limitan y paginan igual que cualquier listado.

## Subida reanudable

1. `POST /uploads` crea sesión con longitud y metadatos del destino.
2. `HEAD /uploads/{id}` devuelve `Upload-Offset` y `Upload-Length`.
3. `PATCH /uploads/{id}` envía bytes desde el offset exacto; Nginx no bufferiza.
4. `POST /uploads/{id}/complete` valida tamaño, detecta tipo y publica el blob.

La subida de carpeta se expresa enviando rutas relativas normalizadas como
metadato por archivo; el servidor crea carpetas de forma idempotente. Cada
segmento se valida y ninguna ruta se usa como ruta física.

## Contenido y Range

`GET /entries/{id}/content` autoriza y registra apertura una sola vez, y delega
la entrega a una ubicación interna de Nginx. Se soportan `Range`, `If-Range`,
`ETag`, respuestas `206` y `416`, `Accept-Ranges: bytes`, y disposición
`inline` para formatos seguros. El cliente nunca recibe una ruta del host.

## Conflictos y asincronía

Conflictos de nombre responden `409` con alternativas explícitas; no se
renombra silenciosamente. Operaciones pequeñas pueden devolver el recurso.
Copias recursivas, vaciado de papelera y trabajos de medios devuelven `202` con
un recurso job consultable.
