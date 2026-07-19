# Contrato REST

## Convenciones

- Base: `/api/v1`.
- JSON en UTF-8; fechas RFC 3339 UTC; tamaños en bytes; ids UUID.
- Toda respuesta JSON usa el mismo envelope: `data`, `error` y `meta`.
- `error` incluye `code`, `message` y errores de campo opcionales; los detalles
  internos nunca salen de la API.
- `X-Request-ID` aceptado o generado y devuelto.
- ETag y Last-Modified permiten revalidar lecturas de metadatos.
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

## Recursos implementados

| Área | Rutas principales |
|---|---|
| Sesión | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/sessions/revoke-all`, `GET /auth/session` |
| Navegación | `GET /storage/folders/{folder_id}/entries`, `GET /storage/files/{file_id}` |
| Contenido | `GET/HEAD /storage/files/{file_id}/content` |
| Carpetas | `POST /storage/folders` |
| Mutaciones | `PATCH /storage/entries/{id}`, `POST /storage/entries/{id}/move`, `POST /storage/entries/{id}/copy`, `POST /storage/entries/{id}/trash` |
| Papelera | `POST /storage/trash/{id}/restore`, `DELETE /storage/trash/{id}` |
| Subidas | `POST /storage/uploads`, `HEAD/PATCH/DELETE /storage/uploads/{id}`, `POST /storage/uploads/{id}/complete` |

## Recursos previstos

| Área | Rutas principales |
|---|---|
| Búsqueda | `GET /search` |
| Actividad | `GET /recents`, `PUT /favorites/{id}`, `DELETE /favorites/{id}`, `GET /favorites` |
| Papelera | `GET /trash`, `DELETE /trash` |
| Medios | `GET /entries/{id}/thumbnail`, `GET /entries/{id}/preview`, `GET /jobs/{id}` |

La especificación OpenAPI concreta y validada se genera desde FastAPI a medida
que se implementan los casos de uso. Swagger UI y ReDoc consumen ese documento;
no habrá documentación manual de endpoints que pueda divergir. Este archivo
solo fija convenciones arquitectónicas, no duplica schemas operativos.

## Listados y cursores

Todos los listados requieren `limit` (por defecto 50, máximo 200) y devuelven
`items` más `next_cursor`. No existe endpoint que entregue el árbol completo.

Los cursores son opacos y versionados; contienen el último valor de orden y el
id de desempate, y quedan ligados al orden y dirección solicitados. Orden
soportado: `name`, `date`, `size` y `type`, ascendente o descendente. Cada orden
añade siempre `id` como desempate estable.

La navegación restringe por carpeta y propietario; acepta nombre, extensión,
clase de entrada, intervalos de fecha y tamaño. Las consultas se limitan y
paginan incluso sin filtros.

## Subida reanudable

1. `POST /storage/uploads` crea sesión con longitud y metadatos del destino.
2. `HEAD /storage/uploads/{id}` devuelve `Upload-Offset` y `Upload-Length`.
3. `PATCH /storage/uploads/{id}` envía bytes desde el offset exacto.
4. `POST /storage/uploads/{id}/complete` valida tamaño, MIME y SHA-256, y
   publica el objeto atómicamente.
5. `DELETE /storage/uploads/{id}` cancela y elimina staging.

La subida de carpetas completas se añadirá en un incremento posterior. Ningún
nombre lógico se utiliza como ruta física.

## Contenido y Range

`GET /storage/files/{id}/content` autoriza, verifica el objeto y lo transmite
actualmente mediante FastAPI. Soporta rangos únicos/múltiples, ETag,
Last-Modified y precondiciones. `HEAD` devuelve los mismos metadatos sin body.

La estrategia de entrega puede devolver en el futuro `X-Accel-Redirect` hacia
una ubicación Nginx `internal`, sin cambiar el caso de uso. El nombre se envía
como `attachment` UTF-8 y el cliente nunca recibe una ruta del host.

## Conflictos y asincronía

Conflictos de nombre responden `409` con alternativas explícitas; no se
renombra silenciosamente. Operaciones pequeñas pueden devolver el recurso.
Copias recursivas, vaciado de papelera y trabajos de medios devuelven `202` con
un recurso job consultable.
