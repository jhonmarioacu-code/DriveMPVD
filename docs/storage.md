# Almacenamiento y transferencias

## Layout físico

Todo el contenido persistente reside bajo `/data/storage`, montado como volumen
del host. El repositorio y las imágenes de contenedor no contienen archivos del
usuario.

```text
/data/storage/
  objects/aa/bb/<uuid>       blobs finalizados
  derivatives/aa/bb/<uuid>   miniaturas y previews regenerables
  staging/<upload-uuid>      subidas incompletas
  quarantine/                reservado para antivirus futuro
  lost+found/                huérfanos aislados por reconciliación
```

Los dos niveles de shard evitan directorios con cientos de miles de entradas.
Las claves son generadas por el servidor y no conservan nombre o extensión.
Las carpetas del explorador son lógicas: no se crean directorios equivalentes
en disco.

## Garantías del adaptador

La aplicación declara el puerto `FileStorageProvider`. Los casos de uso solo
conocen ese contrato; `LocalFileStorageProvider` es el primer adaptador. S3 o
MinIO podrán añadirse seleccionando otro adaptador en el composition root, sin
modificar dominio ni aplicación. El contrato trabaja con iteradores asíncronos
de bytes, rangos y handles opacos; nunca recibe rutas del sistema.

- Resuelve claves opacas y verifica que permanezcan bajo la raíz configurada.
- Escribe staging y objeto final en el mismo filesystem para renombrado atómico.
- Nunca sobrescribe un blob existente; las claves son inmutables.
- Separa publicación, eliminación y reconciliación con operaciones idempotentes.
- Ningún método acepta o devuelve el archivo completo como `bytes`; todos los
  flujos aplican backpressure y memoria acotada.

## Subidas grandes

El cliente divide archivos en bloques configurables y conserva la sesión para
reanudar. El servidor escribe secuencialmente en staging, ejecuta `fsync` y
confirma el offset después de persistir bytes y metadatos. No ensambla chunks
en RAM. Al finalizar recorre staging por streaming para SHA-256 y MIME, y mueve
el archivo con `os.replace`.

Nginx usará `proxy_request_buffering off` solo en la ruta de chunks, con timeout
y límites apropiados. La API leerá el body como stream con backpressure. Las
sesiones expiran y un job limpia staging antiguo.

## Descargas y streaming

FastAPI valida sesión, versión, estado y existencia física antes de iniciar el
stream. La entrega actual usa iteradores asíncronos con memoria acotada. Una
estrategia inyectada permite sustituirla posteriormente por `X-Accel-Redirect`
hacia una ubicación Nginx `internal`.

Los nombres solo se usan en `Content-Disposition` UTF-8. El cache es privado y
el ETag combina checksum, versión y modificación. Se admiten rangos únicos,
sufijos y respuestas multipart, permitiendo audio, video y PDF incrementales.

## Miniaturas

Las miniaturas son derivados cacheables y regenerables:

- imágenes: orientación EXIF aplicada, perfil seguro y límites de píxeles;
- videos: fotograma mediante FFmpeg con timeout;
- PDFs: primera página mediante renderizador con límites.

La solicitud devuelve el derivado si existe o agenda un job idempotente. El
explorador muestra un placeholder mientras se procesa.

## Backup

El conjunto esencial es PostgreSQL más `objects`. `staging` y `derivatives` se
excluyen. Para consistencia se toma primero un snapshot/backup coordinado de
metadatos y objetos o se detienen escrituras durante la ventana. Nunca se
considera válido un backup hasta restaurarlo y verificar referencias y hashes
muestreados.
