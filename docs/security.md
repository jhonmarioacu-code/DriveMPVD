# Modelo de seguridad

## Alcance y amenazas

El sistema es privado pero accesible por navegador. Se protege contra robo de
sesión, CSRF, fuerza bruta, path traversal, archivos hostiles, abuso de rango,
inyección y exposición accidental del almacenamiento. No se considera seguro
publicar `/data/storage` como un directorio estático.

## Identidad y sesión

- Una cuenta administradora creada por un comando de bootstrap; no hay registro.
- Contraseña con Argon2id y parámetros calibrados al servidor; rehash al login
  cuando cambie la política.
- Access JWT corto (objetivo 15 minutos) en cookie `HttpOnly`, `Secure` y
  `SameSite=Lax`.
- Refresh JWT rotatorio en cookie separada; solo un HMAC del token vigente se
  persiste. Reutilizar un token anterior revoca inmediatamente su familia.
- JWT con `iss`, `aud`, `sub`, `iat`, `nbf`, `exp` y `jti`; algoritmo y claves
  fijados por configuración, sin aceptar el algoritmo del token.
- Logout, detección de reutilización y revocación administrativa actualizan
  sesiones persistidas. El cambio de contraseña
  revoca todas.

Los secretos solo se inyectan por archivos Docker secrets o variables de
entorno protegidas. Nunca se incluyen valores reales en Git ni imágenes.

## CSRF y navegador

Toda mutación exige token CSRF ligado a la sesión en cabecera y valida
`Origin`/`Host`. CORS queda deshabilitado por defecto porque frontend y API
comparten origen. Las peticiones simples no modifican estado.

Cabeceras mínimas en Nginx: HSTS tras habilitar TLS, CSP restrictiva,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, permisos del
navegador restringidos y protección de framing con CSP `frame-ancestors`.

## Rate limiting

Nginx aplica zonas compartidas por IP con límites estrictos a login/refresh y
límites de ráfaga razonables a API y contenido. La aplicación añade bloqueo
temporal progresivo del login en PostgreSQL. Los límites de streaming se
configuran separados para no interrumpir reproducción válida.

## Validación de archivos y rutas

- El nombre es un value object: longitud acotada, Unicode normalizado, sin NUL,
  `/`, `\\`, `.` o `..`, ni nombres reservados de control.
- Las rutas relativas de carpetas se dividen y validan segmento por segmento.
- El contenido se almacena con claves UUID generadas por servidor. Ningún
  nombre, extensión o ruta del cliente participa en `open()`.
- El adaptador resuelve y comprueba que toda ruta final pertenece a una raíz
  permitida; no sigue symlinks creados externamente.
- Se limita longitud declarada, longitud real, número de chunks, headers y
  metadatos. Una subida que excede 50 GB se cancela y elimina de staging.
- MIME declarado es informativo; el servidor detecta contenido y sirve tipos
  peligrosos como adjunto. SVG/HTML no se muestran inline en el origen principal.
- La entrega de bytes actual fija `X-Content-Type-Options: nosniff`; Nginx la
  reforzará junto con el resto de cabeceras de producción en la Fase 8.
- ZIP, RAR y 7Z se tratan como blobs; no se extraen automáticamente.

El escaneo ClamAV será un módulo posterior. Hasta entonces no se ejecuta
contenido subido ni se confía en macros o codecs fuera de procesos aislados y
con límites.

## Procesamiento de medios futuro

No hay worker de medios operativo todavía. Cuando se incorpore, FFmpeg y los
renderizadores recibirán solo claves internas, se ejecutarán sin red, con
usuario no privilegiado, límites de CPU/memoria/tiempo y salida controlada. Los
fallos generarán una miniatura genérica y un error sanitizado. La estrategia
actual de placeholders no ejecuta ni procesa contenido subido en el cliente.

## Contenedores y host

- Procesos sin root, filesystem de contenedor de solo lectura cuando sea viable.
- PostgreSQL no se publica a Internet; red interna de Compose.
- Nginx es el único puerto público. TLS moderno y certificados renovables.
- `/data/storage` se monta solo donde sea imprescindible; el frontend no lo ve.
- Backups se cifran y se prueba su restauración.

Antes del despliegue público se ejecutará una lista de comprobación OWASP ASVS
aplicable, análisis de dependencias y revisión de la configuración generada.
