# ADR-0012: Streaming RFC 9110 y estrategia de entrega

- Estado: aceptado
- Fecha: 2026-07-18

## Contexto

Las descargas deben servir objetos de hasta 50 GB, permitir reanudación y
reproducción multimedia, y evolucionar desde FastAPI hacia Nginx, S3 o MinIO
sin modificar dominio ni autorización.

## Decisión

- `PrepareFileDownloadUseCase` autoriza, resuelve la versión inmutable y exige
  que `FileStorageProvider.stat` confirme existencia y tamaño físico.
- El adaptador HTTP evalúa `If-Match`, `If-None-Match` e
  `If-Modified-Since` antes de interpretar `Range`.
- Se implementan rangos únicos, sufijos, rangos abiertos y hasta 16 rangos
  múltiples. Rangos solapados o adyacentes se consolidan.
- Múltiples rangos producen `multipart/byteranges` con longitud calculada sin
  materializar el cuerpo.
- `DownloadDeliveryProvider` selecciona streaming ASGI. Un adaptador futuro
  podrá devolver una URI interna y activar `X-Accel-Redirect`.
- El ETag fuerte combina checksum, versión y modificación de metadatos.
- El cuerpo se envuelve para medir bytes, duración, velocidad y cancelación.

## Consecuencias

- FastAPI nunca carga el archivo completo y el mismo puerto podrá emitir rangos
  desde almacenamiento local, S3 o MinIO.
- `HEAD` y `GET` comparten autorización, precondiciones y cabeceras.
- Los errores previos al cuerpo conservan el envelope JSON; una falla física
  posterior al inicio del stream solo puede cerrar la conexión.
- `X-Accel-Redirect` queda preparado pero deshabilitado hasta que un adaptador
  lo active y se pruebe contra la ubicación Nginx `internal` ya configurada.
- Las métricas cuentan bytes cedidos al servidor ASGI, no confirmaciones TCP.
