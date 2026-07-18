# Fase 2.6: sistema de subida de archivos

- Estado: implementado y validado
- Fecha: 2026-07-18

## Entregado

- Inicio, consulta de offset, append, reanudación, finalización y cancelación.
- Streaming ASGI → caso de uso → `FileStorageProvider`, sin buffer completo.
- Adaptador local confinado, staging, `fsync` y publicación atómica.
- SHA-256 por chunk y SHA-256 completo durante la verificación final.
- Validación de tamaño declarado/real, nombre, ruta lógica, extensiones y MIME.
- Persistencia transaccional de sesión, objeto, archivo y versión.
- Compensación por truncado/borrado entre filesystem y PostgreSQL.
- Puerto opcional `VirusScanner`, sin implementación ni escaneo activo.
- Métricas JSON: operación, resultado, duración, bytes, velocidad y error.

## Protocolo HTTP

| Método | Ruta | Función |
|---|---|---|
| `POST` | `/api/v1/storage/uploads` | Iniciar sesión. |
| `HEAD` | `/api/v1/storage/uploads/{upload_id}` | Consultar offset y estado. |
| `PATCH` | `/api/v1/storage/uploads/{upload_id}` | Añadir chunk. |
| `POST` | `/api/v1/storage/uploads/{upload_id}/complete` | Verificar y publicar. |
| `DELETE` | `/api/v1/storage/uploads/{upload_id}` | Cancelar y limpiar. |

El `PATCH` exige `application/offset+octet-stream`. OpenAPI lo documenta como
body binario y conserva autenticación Bearer/cookie y CSRF.

## Configuración

- `DRIVEMPVD_MAX_UPLOAD_SIZE_BYTES`
- `DRIVEMPVD_MAX_UPLOAD_CHUNK_SIZE_BYTES`
- `DRIVEMPVD_UPLOAD_SESSION_TTL_SECONDS`
- `DRIVEMPVD_MAX_LOGICAL_PATH_LENGTH`
- `DRIVEMPVD_UPLOAD_ALLOWED_EXTENSIONS`
- `DRIVEMPVD_UPLOAD_BLOCKED_EXTENSIONS`
- `DRIVEMPVD_UPLOAD_ALLOWED_MIME_TYPES`

Las listas se expresan como arrays JSON en variables de entorno.

## Migraciones

No se creó migración. `upload_sessions` pertenece a `20260718_0003`; Alembic
no detectó drift.

## Validación

| Control | Resultado |
|---|---|
| Black | Sin cambios requeridos |
| Ruff | Sin incidencias |
| MyPy estricto | Sin incidencias |
| Pytest | 93 pruebas superadas |
| Cobertura líneas/ramas | 90,48 %; mínimo 90 % |
| PostgreSQL | 16.14 real |
| Alembic | downgrade/upgrade/check sin drift |

Las pruebas incluyen archivo pequeño, archivo de 5 MiB en cinco chunks,
reanudación, cancelación, límites, MIME incompatible, rollback y publicación.

## Riesgos y recomendaciones

- Implementar reconciliación periódica entre staging, objetos y PostgreSQL
  para cubrir terminaciones abruptas entre recursos transaccionales.
- Ampliar la detección conservadora por firmas cuando se habiliten más formatos.
- Medir la verificación con archivos cercanos a 50 GB; hoy mantiene un lock de
  fila durante la lectura completa.
- Configurar Nginx con `proxy_request_buffering off` solo para PATCH de chunks.
- Añadir S3/MinIO y el scanner sin cambiar los casos de uso.
