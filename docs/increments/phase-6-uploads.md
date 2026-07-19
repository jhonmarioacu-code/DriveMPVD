# Fase 6: subidas normales y reanudables

- Estado: implementado y validado
- Fecha: 2026-07-18

## Alcance de la implementación

- Selección de uno o varios archivos desde el explorador y zona de
  arrastrar-y-soltar asociada a la carpeta abierta.
- Bandeja visible y responsive con nombre, bytes transferidos, progreso
  accesible y los estados `pendiente`, `subiendo`, `completado`, `error` y
  `cancelado`.
- Cancelación local inmediata, cancelación remota de la sesión cuando ya fue
  creada, descarte de resultados terminales y reintento explícito de errores o
  cargas canceladas.
- Cola con un máximo de dos archivos concurrentes. Cada archivo usa el mismo
  protocolo reanudable, también cuando es pequeño; el cliente lo divide con
  `Blob.slice()` en bloques de 4 MiB, por debajo del límite actual del servidor
  de 16 MiB.
- Reanudación dentro de la sesión de la SPA: un reintento consulta el `HEAD`
  de la sesión y continúa desde el offset confirmado por el servidor. Un
  conflicto `storage.upload_offset_mismatch` también se reconcilia mediante
  `HEAD`, para no repetir ni saltar bytes.
- Al completar una sesión se invalida la caché TanStack Query del explorador,
  para que el archivo publicado aparezca al volver a consultar la carpeta.

No se añadió un endpoint ni se modificó el backend: el contrato de la Fase 2.6
ya cubría la carga por partes, la reanudación y la publicación atómica.

## Contrato backend/frontend verificado

Todos los recursos están bajo `/api/v1` y mantienen el envelope JSON habitual,
salvo `HEAD`, que responde sin cuerpo.

| Método y ruta                                | Petición del cliente                                               | Respuesta que usa el frontend                                                                                                         |
| -------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /storage/uploads`                      | JSON `{ parent_id, filename, size, mime_type }`                    | Sesión de subida; `201`, `Location`, `Upload-Offset` y `Upload-Length`.                                                               |
| `HEAD /storage/uploads/{upload_id}`          | Cookie de sesión                                                   | `204` con `Upload-Offset`, `Upload-Length`, `Upload-Status` y `Upload-Expires`.                                                       |
| `PATCH /storage/uploads/{upload_id}`         | Bytes `application/offset+octet-stream` y cabecera `Upload-Offset` | Resultado de chunk y nuevo offset. Un `409 storage.upload_offset_mismatch` incluye el offset esperado en la cabecera `Upload-Offset`. |
| `POST /storage/uploads/{upload_id}/complete` | Petición vacía                                                     | Archivo publicado tras validar longitud, MIME y checksum.                                                                             |
| `DELETE /storage/uploads/{upload_id}`        | Petición vacía                                                     | Sesión cancelada y staging limpiado.                                                                                                  |

El frontend valida que las cabeceras de `HEAD` sean enteros no negativos y que
el estado esté entre `created`, `uploading`, `completed`, `cancelled` o
`expired`. Una respuesta de protocolo inválida se trata como error del cliente,
en vez de continuar con un offset no confiable.

## Seguridad e integración de sesión

- El adaptador de subida se construye sobre el cliente HTTP centralizado de la
  Fase 4. Conserva `credentials: include`, cookies HttpOnly y la renovación
  serializada ante un `401` antes de repetir una petición.
- `POST`, `PATCH` y `DELETE` reciben `X-CSRF-Token` desde la cookie pública
  configurada; `HEAD` no es una mutación y no requiere ese token. Las llamadas
  permanecen en mismo origen por defecto.
- Se usa `XMLHttpRequest` exclusivamente para los chunks porque expone el
  progreso de subida; conserva `withCredentials` y las mismas cabeceras CSRF
  que el cliente basado en `fetch`.
- La bandeja no persiste credenciales, JWT, contenido ni cookies. Sus
  controladores `AbortController` se abortan al cancelar o desmontar la SPA.
- El servidor sigue siendo la autoridad de límites, autorización de la carpeta,
  nombre, MIME, checksum y publicación. El navegador nunca forma rutas físicas
  ni decide el offset definitivo.

## Límite deliberado: carpetas completas

No se expone selección de carpetas en esta fase. La API actual solo inicia una
sesión para un archivo y un `parent_id`; no acepta rutas relativas ni una
operación atómica para crear la jerarquía de destino. Habilitar
`webkitdirectory` o arrastrar una carpeta sin ese contrato obligaría al cliente
a adivinar rutas y a multiplicar mutaciones no transaccionales.

La carga de carpetas queda pendiente de un incremento posterior que defina el
contrato de árbol, las reglas de conflicto y la validación de cada segmento.

## Semántica de reanudación

La reanudación es segura frente a un fallo de red, un error recuperable o un
desfase de offset mientras la página conserva el archivo seleccionado y el id
de sesión en memoria. No se promete reanudar automáticamente después de una
recarga completa del navegador: el navegador no conserva de forma portable un
`File` ni permiso de lectura reutilizable. Esa capacidad requeriría un diseño
explícito de persistencia y permisos (por ejemplo, File System Access API), y
no se simula en esta fase.

El reintento se solicita de forma explícita por la persona usuaria. Esto evita
repetir automáticamente una operación que el servidor ya pudo haber publicado;
antes de enviar otro chunk se reconcilia el offset del servidor.

## Validación de cierre

| Control                                   | Resultado                                                                                    |
| ----------------------------------------- | -------------------------------------------------------------------------------------------- |
| Prettier (`npm run format`)               | Correcto, sin diferencias.                                                                   |
| ESLint (`npm run lint`)                   | Correcto, sin incidencias ni advertencias.                                                   |
| TypeScript estricto (`npm run typecheck`) | Correcto.                                                                                    |
| Vitest y cobertura (`npm run test`)       | 87 pruebas correctas; 91,04 % sentencias, 80,59 % ramas, 90,94 % funciones y 93,06 % líneas. |
| Build de producción (`npm run build`)     | Correcto; JS 422,99 kB (132,28 kB gzip) y CSS 34,26 kB (7,31 kB gzip).                       |
| Backend: Black, Ruff y MyPy               | Correcto; 133 archivos Python verificados.                                                   |
| Backend: Pytest sin cobertura             | 80 superadas y 26 omitidas por no haber PostgreSQL externo.                                  |

Las pruebas de frontend cubren el contrato de cada endpoint, progreso por
chunk, cancelación, reintento/reconciliación de offset, cola concurrente,
estados accesibles de la bandeja, cabeceras CSRF, cookies y repetición tras un
`401`. Las pruebas de backend existentes de la Fase 2.6 ejercen streaming,
límites, reanudación, cancelación, checksum y publicación; no se requiere una
migración ni un cambio de contrato para esta fase.

## Incidencia de entorno conocida

`python -m pytest -q` también ejecuta el umbral global de cobertura del backend
(90 %). En este entorno, sus 26 pruebas de integración PostgreSQL están omitidas
porque no hay un PostgreSQL externo disponible; por ello la orden termina con
`62,15 %`, aunque sus 80 pruebas ejecutables pasan. No se atribuye a la Fase 6
ni se modifica el umbral: la validación completa de cobertura del backend queda
para un entorno con PostgreSQL 16.

## Siguiente fase

La Fase 7 (visualizadores y miniaturas) no se inicia automáticamente. Requiere
aprobación explícita después de este cierre.
