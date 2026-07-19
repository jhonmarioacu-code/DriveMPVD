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

Nginx aplica `proxy_request_buffering off` sólo a la ruta de chunks, con
timeouts de una hora y límites configurables. La API lee el body como stream
con backpressure. Las sesiones expiran y un job limpia staging antiguo.

## Descargas y streaming

FastAPI valida sesión, versión, estado y existencia física antes de iniciar el
stream. La entrega actual usa iteradores asíncronos con memoria acotada. Una
estrategia inyectada permite sustituirla posteriormente por `X-Accel-Redirect`
hacia una ubicación Nginx `internal`; la ubicación y un overlay de montaje de
sólo lectura ya están preparados, pero no se habilitan hasta validar ese
adaptador con `HEAD`, ETag, descargas autenticadas y rangos.

Los nombres solo se usan en `Content-Disposition` UTF-8. El cache es privado y
el ETag combina checksum, versión y modificación. Se admiten rangos únicos,
sufijos y respuestas multipart, permitiendo audio, vídeo y PDF incrementales.
La disposición predeterminada es `attachment`; `?disposition=inline` solo se
honra para una lista de MIME seguros de imagen raster, audio, vídeo y PDF. La
cabecera `X-Content-Type-Options: nosniff` acompaña la entrega. De este modo un
tipo activo como HTML o SVG no se incrusta en el origen de la aplicación aunque
la URL lo solicite.

El frontend consulta `HEAD` antes de abrir una vista y usa el mismo `GET` para
los elementos nativos del navegador. Por tanto el streaming no duplica bytes
en la SPA y mantiene las cookies de sesión, ETag y Range del contrato existente.

## Miniaturas y derivados

El layout, modelos y puertos reservan derivados cacheables y regenerables, pero
no hay todavía un endpoint de miniaturas ni worker de medios operativo. En
particular, esta versión no ejecuta FFmpeg, un renderizador PDF ni una tarea que
devuelva o agende `GET /entries/{id}/thumbnail`.

La Fase 7 aplica mientras tanto una estrategia de cliente acotada: las imágenes
raster de hasta 1 MiB se cargan perezosamente como fuente `inline`; vídeos,
PDF, imágenes grandes, tamaños desconocidos y fallos usan placeholders. No se
descarga un objeto grande para crear una miniatura local.

Cuando se implemente el servicio de derivados, deberá generar imágenes con
orientación EXIF aplicada, perfil seguro y límite de píxeles; fotogramas de
vídeo con FFmpeg aislado y timeout; y primera página de PDF con un renderizador
con límites. La solicitud podrá devolver un derivado existente o un job
idempotente, manteniendo el placeholder durante el procesamiento.

## Backup

El conjunto esencial es PostgreSQL más `objects`. `staging` y `derivatives` se
excluyen. Para consistencia se toma primero un snapshot/backup coordinado de
metadatos y objetos o se detienen escrituras durante la ventana. Nunca se
considera válido un backup hasta restaurarlo y verificar referencias y hashes
muestreados.
