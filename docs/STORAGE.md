# Gestión del almacenamiento de archivos

## 1. Principio

Los archivos de usuario se almacenan físicamente en la VPS bajo
`/data/storage`. El repositorio, la imagen y PostgreSQL no contienen el
contenido binario. PostgreSQL conserva metadatos y referencias.

```text
/data/storage/
  objects/aa/bb/<uuid>       blobs finalizados
  derivatives/aa/bb/<uuid>   previews y thumbnails regenerables
  staging/<upload-uuid>      subidas incompletas
  quarantine/                reservado para antivirus futuro
  lost+found/                huérfanos aislados por reconciliación
```

El árbol visible por el usuario es lógico. Nunca cree directorios físicos que
imiten carpetas de catálogo ni use un nombre enviado por cliente como ruta.

## 2. `FileStorageProvider`

Application consume un puerto de storage que:

- opera con iteradores asíncronos, rangos y handles opacos;
- resuelve keys sin salir de la raíz configurada;
- no materializa un archivo entero como `bytes`;
- evita sobrescribir blobs finales;
- publica, elimina y reconcilia de manera idempotente;
- permite adaptar storage local, S3 o MinIO sin cambiar dominio.

El adaptador local actual usa keys UUID opacas con dos niveles de shard. No
seguir symlinks creados externamente ni exponer paths del host.

## 3. Subidas reanudables

### Flujo

1. Cliente crea `UploadSession` con carpeta, nombre, tamaño y MIME declarado.
2. Cliente consulta `HEAD` para offset/estado cuando necesita reanudar.
3. `PATCH` acepta solo el offset confirmado y body
   `application/offset+octet-stream`.
4. API transmite el chunk a staging con backpressure y confirma offset tras
   persistir bytes y metadatos.
5. Completar recorre staging por streaming para SHA-256 y detección MIME.
6. El adaptador hace `fsync`, verifica tamaño y usa `os.replace` atómico.
7. Se confirman metadatos de objeto/archivo/versión.

El staging y objeto final deben estar en el mismo filesystem. Si falla el
commit de append, se trunca al offset previo; si falla el commit posterior a
publicar, se compensa el objeto final de forma controlada.

### Límites y seguridad

- Tamaño máximo inicial: 50 GiB, configurable.
- Chunk máximo de servidor: configurable; frontend usa chunks de 4 MiB.
- Se validan nombre, ruta lógica, tamaño declarado/real, número de chunks,
  MIME y headers.
- MIME declarado es informativo; el servidor detecta contenido.
- ZIP/RAR/7Z se tratan como blobs; no se extraen automáticamente.
- El scanner antivirus es un puerto previsto, sin implementación activa.

No eliminar staging manualmente. La limpieza de staging vencido y sesiones
expiradas no está implementada y requiere un reconciliador soportado.

## 4. Descargas, streaming y Range

La API valida sesión, autorización, versión, estado y existencia física antes
de responder. El streaming actual ocurre en FastAPI con memoria acotada.

Se soportan:

- `GET` y `HEAD`;
- ETag fuerte y `Last-Modified`;
- `If-Match`, `If-None-Match` e `If-Modified-Since`;
- Range único, abierto, sufijo y multipart limitado;
- `200`, `206`, `304`, `412` y `416` según contrato.

La disposición por defecto es `attachment`. `inline` se permite solo para MIME
seguros de PDF, imagen raster, audio y vídeo. `X-Content-Type-Options:
nosniff` acompaña la entrega; HTML, SVG y tipos activos no deben incrustarse
en el origen de la aplicación.

`X-Accel-Redirect` está preparado mediante overlay de Nginx, pero desactivado.
No activarlo hasta comprobar autorización, `HEAD`, ETag, Range, cancelación,
memoria y benchmark bajo carga.

## 5. Preview y thumbnails

La SPA hace `HEAD` antes de abrir preview inline y usa el mismo `GET`
autenticado para elementos nativos. Esto conserva cookies, ETag y Range sin
duplicar bytes en estado React.

Política actual de miniaturas:

1. Una imagen raster conocida de hasta 1 MiB puede cargarse inline de forma
   perezosa.
2. PDF, vídeo, audio, tamaños desconocidos, imágenes grandes o errores usan
   placeholder.
3. No se descarga un blob grande para fabricar miniatura en navegador.

No existe endpoint de derivados ni worker de medios. No afirmar que PDF/vídeo
se renderizan en servidor, ni introducir FFmpeg/renderizadores sin sandbox,
límites CPU/memoria/tiempo/red y contrato de recuperación.

## 6. Integridad y limpieza

La purga nunca borra bytes primero. Publica un evento durable y el worker:

- decide elegibilidad por referencias en PostgreSQL;
- elimina metadata elegible;
- emite evento de borrado físico;
- borra el objeto idempotentemente.

La base de datos y el filesystem no tienen transacción distribuida; staging,
outbox, compensación y restore drill son mecanismos de consistencia. Ante una
discrepancia, preservar evidencia y tratarla como incidente; no “arreglar” con
`rm`.

## 7. Backup

El backup consistente actual incluye PostgreSQL y todo el árbol de storage,
incluido `objects` y `staging`. Los derivados solo podrían excluirse tras
demostrar que son regenerables y documentar cómo se recuperan.

Consulte [BACKUP.md](BACKUP.md) para procedimiento coordinado y
[DATABASE.md](DATABASE.md) para referencias/metadatos.
