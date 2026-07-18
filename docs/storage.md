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
conocen ese contrato; `LocalFileStorageProvider` será el primer adaptador. S3 o
MinIO podrán añadirse seleccionando otro adaptador en el composition root, sin
modificar dominio ni aplicación. El contrato trabaja con iteradores asíncronos
de bytes, rangos y handles opacos; nunca recibe rutas del sistema.

- Abre archivos usando una raíz preabierta o una ruta resuelta y confinada.
- Rechaza symlinks y tipos especiales.
- Escribe staging y objeto final en el mismo filesystem para renombrado atómico.
- Aplica permisos mínimos y `umask` restrictiva.
- Nunca sobrescribe un blob existente; las claves son inmutables.
- Separa publicación, eliminación y reconciliación con operaciones idempotentes.
- Ningún método acepta o devuelve el archivo completo como `bytes`; todos los
  flujos aplican backpressure y memoria acotada.

## Subidas grandes

El navegador divide archivos en bloques configurables y conserva la sesión
para reanudar. El servidor escribe secuencialmente en staging y confirma el
offset después de que los bytes sean persistentes. No ensambla chunks en RAM ni
duplica un archivo de 50 GB al finalizar.

Nginx usará `proxy_request_buffering off` solo en la ruta de chunks, con timeout
y límites apropiados. La API leerá el body como stream con backpressure. Las
sesiones expiran y un job limpia staging antiguo.

## Descargas y streaming

FastAPI valida sesión, estado y permisos implícitos; luego responde con
`X-Accel-Redirect` hacia una ubicación Nginx `internal`. Nginx entrega el blob
con zero-copy cuando el sistema lo permita y gestiona rangos sin cargarlo en
Python.

Los nombres solo se usan en `Content-Disposition` con codificación segura. El
cache privado y ETag se basan en identidad/revisión del blob. La reproducción
de audio y video solicita rangos; abrir un PDF no descarga anticipadamente el
archivo completo si el visor solicita rangos.

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
