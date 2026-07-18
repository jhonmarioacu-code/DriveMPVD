# ADR-0011: Staging reanudable y publicación atómica

- Estado: aceptado
- Fecha: 2026-07-18

## Contexto

Los archivos pueden alcanzar 50 GB, la conexión puede interrumpirse y ningún
caso de uso debe materializar contenido completo en memoria. PostgreSQL y el
filesystem no comparten una transacción distribuida. SHA-256 debe ser correcto
incluso cuando la subida se reanuda en otro proceso.

## Decisión

- Cada `UploadSession` corresponde a un objeto opaco en `staging`.
- `PATCH` solo acepta el `Upload-Offset` persistido y limita cada petición. El
  cuerpo se transmite directamente a `FileStorageProvider`.
- Cada chunk calcula SHA-256 durante la recepción. Al finalizar se vuelve a
  recorrer staging por streaming para obtener el digest completo y detectar
  MIME. El estado interno de SHA-256 no se serializa entre reanudaciones.
- El adaptador local hace `fsync`, verifica tamaño y publica con `os.replace`
  dentro del mismo filesystem.
- El lock de fila serializa append/finalización. Si falla el commit de un
  append, staging se trunca al offset previo; si falla el commit posterior a
  publicar, el objeto final se elimina de forma compensatoria.
- `VirusScanner` se inyecta opcionalmente antes de publicar. En este incremento
  permanece deshabilitado.
- Las métricas se emiten como logging JSON estructurado.

## Consecuencias

- El uso de memoria queda acotado por el chunk ASGI y un prefijo de inspección
  de 64 KiB.
- Finalizar requiere una lectura secuencial adicional, coste aceptado para
  reanudación portable e integridad fuerte.
- Los objetos finales nunca conservan nombres suministrados por el usuario.
- Local, S3 y MinIO pueden implementar el mismo puerto.
- Una terminación abrupta entre filesystem y commit aún requiere reconciliación
  periódica por UUID. Los errores controlados ejecutan compensación inmediata.
