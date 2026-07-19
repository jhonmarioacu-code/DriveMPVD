# Fase 2.7: descarga y streaming

- Estado: implementado y validado
- Fecha: 2026-07-18

## Entregado

- `GET` y `HEAD /api/v1/storage/files/{file_id}/content`.
- Streaming completo y por rangos mediante `FileStorageProvider`.
- Rangos únicos y `multipart/byteranges` conforme a RFC 9110.
- Respuestas 200, 206, 304, 412 y 416.
- Cabeceras de rango, caché, validación y nombre UTF-8.
- `If-Match`, `If-None-Match` e `If-Modified-Since`.
- Verificación física previa al stream y errores uniformes.
- Métricas JSON de duración, bytes, velocidad, errores y cancelaciones.
- Estrategia separada preparada para `X-Accel-Redirect`.

## Semántica Range

- `bytes=0-99`, `bytes=100-` y `bytes=-100` están soportados.
- Si ningún miembro es válido se responde 416 y `Content-Range: bytes */size`.
- Los rangos solapados se consolidan; más de 16 se rechazan.
- Varios rangos generan un boundary determinista y longitud exacta.

## OpenAPI

OpenAPI documenta GET/HEAD, cabeceras condicionales, ejemplo de `Range` y los
códigos 200/206/304/412/416. `/openapi.json` continúa siendo la fuente única.

## Migraciones

No se creó migración. La revisión vigente sigue siendo `20260718_0003` y
Alembic no detectó drift.

## Validación

| Control                | Resultado                           |
| ---------------------- | ----------------------------------- |
| Black                  | 135 archivos sin cambios requeridos |
| Ruff                   | Sin incidencias                     |
| MyPy estricto          | 135 archivos sin incidencias        |
| Pytest                 | 102 pruebas superadas               |
| Cobertura líneas/ramas | 90,79 %; mínimo 90 %                |
| PostgreSQL             | 16.14 real                          |
| Alembic                | downgrade/upgrade/check sin drift   |

Las pruebas cubren descarga completa, HEAD, rangos, multipart, vacío, 3 MiB,
precondiciones, 416, UTF-8, ausencia física y cancelación del iterador.

## Riesgos y recomendaciones

- Habilitar y medir `X-Accel-Redirect` antes de carga concurrente alta.
- Probar archivos cercanos a 50 GB en Ubuntu/Nginx; la suite usa 3 MiB.
- El límite de 16 rangos reduce amplificación, pero Nginx deberá replicarlo.
- Implementar `stat` y `Range` nativos en futuros adaptadores S3/MinIO.
- Un error físico después de enviar cabeceras no puede convertirse en JSON.
