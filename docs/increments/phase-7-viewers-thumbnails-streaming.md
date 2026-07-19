# Fase 7: visualizadores, miniaturas, streaming y descargas

- Estado: terminada y validada
- Fecha: 2026-07-18

## Alcance entregado

- Acción de **Vista previa** desde el explorador para los formatos que el
  navegador puede representar de forma segura, sin cargar el contenido del
  archivo en el estado JavaScript de la SPA.
- Diálogo responsive y accesible para cada archivo: imágenes con zoom entre
  50 % y 300 % y rotación visual; vídeo y audio mediante controles nativos de
  HTML5; y PDF mediante el visor nativo disponible en el navegador.
- Estados explícitos de preparación, error de autorización/entrega, error del
  elemento multimedia y formato no compatible. En todos los casos se conserva
  una salida de descarga y la posibilidad de abrir el contenido aparte.
- Descarga directa que conserva el comportamiento `attachment` existente; el
  navegador transmite el contenido desde el backend sin almacenarlo en memoria
  de la aplicación.
- Miniaturas acotadas y perezosas en el listado: solo una imagen raster de
  hasta 1 MiB intenta usar el archivo fuente; vídeo, PDF, imágenes mayores y
  cualquier error muestran un placeholder tipado.

Los formatos se clasifican por MIME conocido y, para la presentación, por
extensión. La extensión no relaja la política de seguridad del servidor: una
vista previa solo se muestra si el servidor confirma una entrega `inline`
permitida.

## Contrato de contenido usado por el frontend

El recurso existente sigue siendo el único recurso de bytes:

| Uso                          | Método y ruta                                                     | Disposición                        |
| ---------------------------- | ----------------------------------------------------------------- | ---------------------------------- |
| Descarga                     | `GET /api/v1/storage/files/{file_id}/content`                     | `attachment` por defecto           |
| Comprobación de vista previa | `HEAD /api/v1/storage/files/{file_id}/content?disposition=inline` | Verifica MIME y cabeceras sin body |
| Imagen, audio, vídeo o PDF   | `GET /api/v1/storage/files/{file_id}/content?disposition=inline`  | `inline` solo para un MIME seguro  |

`disposition` admite `attachment` e `inline`. El valor por defecto conserva la
compatibilidad de descargas. `inline` no es una autorización del cliente: el
backend solo lo concede a `application/pdf` y a la lista explícita de MIME de
imagen raster, audio y vídeo admitidos. HTML, SVG, tipos desconocidos y otros
tipos potencialmente activos permanecen como adjuntos aunque se solicite
`inline`.

La comprobación `HEAD` se realiza con `cache: no-store` y exige que la cabecera
`Content-Disposition` recibida sea `inline`; así una extensión conocida no
puede forzar que el navegador trate como vista previa una respuesta de
descarga. Las peticiones son de lectura: no requieren CSRF. Al compartir
origen con la API, los elementos nativos del navegador envían las cookies de
sesión HttpOnly sin exponer tokens a JavaScript. La respuesta incluye además
`X-Content-Type-Options: nosniff` para no delegar la seguridad de la entrega
inline en la futura capa Nginx.

El mismo `GET` conserva `Accept-Ranges`, ETag, Last-Modified, respuestas
condicionales y rangos únicos o múltiples de RFC 9110. Los elementos
`<video>`, `<audio>` y el visor PDF nativo pueden por ello pedir segmentos a
demanda; el frontend no implementa un protocolo de streaming paralelo.

## Estrategia de miniaturas

No existe todavía un endpoint ejecutable de derivados ni un worker de medios
en el backend. Aunque el modelo y los puertos de derivados están preparados,
esta fase no simula un generador ni afirma que se haya procesado un vídeo o un
PDF en servidor.

Como solución segura y de coste acotado, `EntryThumbnail` aplica esta política:

1. Para una imagen raster clasificable y de tamaño conocido menor o igual a
   1 MiB, carga perezosamente el contenido `inline` con `decoding="async"`.
2. Para imagen grande, tamaño desconocido, vídeo, audio, PDF u otro formato,
   muestra un placeholder tipado sin descargar el blob original solo para
   obtener una miniatura.
3. Si la imagen fuente no puede servirse `inline` o falla al cargar, cambia al
   mismo placeholder.

Esta política evita que las filas del explorador descarguen por anticipado
archivos grandes. Una fase posterior podrá reemplazar el primer caso por
`GET /entries/{id}/thumbnail` y un job durable, sin cambiar la interfaz de
listado. Esa ampliación deberá definir generación aislada, límites de recursos,
invalidación y almacenamiento de derivados.

## Formatos y límites de experiencia

- Imagen: AVIF, GIF, JPEG, PNG y WebP cuando el navegador y el MIME entregado
  los soportan; el diálogo incluye zoom y rotación.
- Vídeo: MP4, Ogg, QuickTime y WebM mediante `<video controls>` con
  `preload="metadata"`.
- Audio: AAC, FLAC, M4A/MP4, MPEG/MP3, Ogg, WAV y WebM mediante
  `<audio controls>` con `preload="metadata"`.
- PDF: `<iframe>` del visor nativo del navegador con `referrerPolicy="no-referrer"`.
- Otros formatos, o codecs que el navegador no soporte aunque se clasifiquen
  por extensión, conservan el flujo de descarga.

La capacidad de renderizar PDF, codec y contenedor depende del navegador. No
se incorpora PDF.js, FFmpeg ni un worker de transcodificación en esta fase; el
botón de descarga es el fallback obligatorio.

## Validación de cierre

- Frontend: `npm test` correcto con **20 archivos, 161 pruebas** y cobertura de
  **91.16 %** de sentencias, **82.25 %** de ramas, **90.52 %** de funciones y
  **93.18 %** de líneas. `npm run typecheck`, `npm run lint`, `npm run format`
  y `npm run build` también finalizaron correctamente.
- Backend: Black, Ruff y MyPy estricto correctos. `pytest --no-cov -q` terminó
  con **81 correctas y 27 omitidas**; las omitidas requieren el PostgreSQL de
  integración no disponible en este entorno. Las pruebas de integración del
  contrato `inline` quedan preparadas para ejecutarse cuando exista
  `DRIVEMPVD_TEST_DATABASE_URL`.
- La ejecución completa de `pytest -q` conserva la puerta configurada del 90 %
  pero termina con código 1 al alcanzar **62.18 %** de cobertura: sin
  PostgreSQL se omiten las rutas de integración que cubren repositorios y casos
  de uso. No hay prueba funcional fallida; la incidencia operativa se debe
  resolver en la validación con base de datos de la Fase 10.

El test unitario de entrega puede sufrir un import circular preexistente si se
ejecuta aislado por orden de importación; la suite completa carga el paquete en
orden válido y finaliza correctamente. No se modificó esa infraestructura
ajena al alcance de la fase.

## Siguiente fase

La Fase 8 (Docker Compose y Nginx) no se inicia automáticamente. Requiere el
cierre validado de esta fase y aprobación explícita.
