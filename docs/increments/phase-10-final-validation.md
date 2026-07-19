# Fase 10: Validación final y documentación operativa

- Estado: implementación y validación local ejecutadas; validación operativa de
  Ubuntu/Docker pendiente de un host con Docker Engine
- Fecha: 2026-07-19

## Alcance validado localmente

- Arranque del ASGI en un intérprete Python limpio, incluyendo una regresión que
  evita el ciclo entre DTOs y puertos detectado durante esta fase.
- Configuración estática de Compose, Nginx, cookies, CSRF, cabeceras, límites de
  subida, TLS de producción y exposición de servicios.
- Smoke test reproducible para el host: SPA, readiness, cabeceras, login por
  cookies, rechazo de mutación sin CSRF, explorador, carpeta, subida reanudable,
  movimiento, PDF inline, `HEAD`, descarga, Range, limpieza y logout.
- Preflight de producción que no imprime secretos y rechaza placeholders,
  cookies inseguras, TLS ausente, límites incoherentes, rutas no preparadas y
  tags de imagen mutables.

## Correcciones aplicadas

- Se eliminó un ciclo de importación que impedía `import app.main` desde un
  proceso limpio.
- El smoke test dejó de depender de `HEAD /health` (esa ruta sólo expone GET),
  usa nombres únicos, limpia recursos y admite contraseña mediante archivo
  protegido sin pasarla por argumentos. Lee puertos desde el archivo Compose,
  exige URL explícita con el nombre del certificado para TLS y verifica
  `HttpOnly`, `SameSite`, `Path` y `Secure` de las cookies.
- Nginx exige TLS en producción, omite query strings de los logs, no propaga
  `X-Forwarded-For` aportado por el cliente, resuelve servicios Docker de forma
  dinámica, limita conexiones de subidas lentas y bloquea source maps públicos.
- Se corrigió la guía de Certbot: el contenedor recibe PEMs dereferenciados en
  `/etc/drivempvd/tls`, con recarga posterior a la renovación.
- La plantilla `docker/.env.production.example` quedó versionada de forma
  explícita; antes estaba excluida por la regla global de archivos `.env`.
- Se añadieron procedimientos de instalación, preflight, backup coordinado,
  restore drill aislado, actualización, rollback, rotación y mantenimiento.
- El preflight rechaza tags de imagen flotantes conocidos y la reutilización de
  un puerto HTTP/HTTPS; la guía ahora incluye la emisión inicial de Certbot y
  la transición a renovación `webroot`.
- La documentación deja claro que no hay worker de reconciliación de staging
  desplegado y que el backup actual incluye el árbol completo de almacenamiento.

## Decisión de X-Accel-Redirect

Permanece desactivado. El proveedor actual continúa con streaming autorizado de
FastAPI, acotado en memoria y cubierto para `HEAD`, ETag y RFC 9110. El overlay
no se activa hasta comparar en el host objetivo ambos modos con 50 GiB,
concurrencia, autorización, Range, cancelación y memoria.

## Resultados de validación local

- Frontend: TypeScript, ESLint, Prettier y build de producción correctos;
  Vitest: 163 pruebas correctas, 91,36 % statements, 82,44 % branches y
  93,42 % líneas.
- Backend: Ruff, Black y MyPy correctos; 92 pruebas correctas y 27 omitidas
  porque requieren PostgreSQL real.
- La ejecución con cobertura confirma 63,42 % total y no supera la puerta de
  90 %. No se redujo el umbral: la evidencia faltante son las integraciones de
  PostgreSQL que este host no puede arrancar.
- El benchmark local de 256 MiB volvió a verificar streaming acotado: 160,92
  MiB/s de append, 542,08 MiB/s de lectura y pico `tracemalloc` de 4 341 787
  bytes en esta ejecución Windows. No es un SLO de producción.
- El preflight rechaza de forma segura la plantilla con placeholders; el
  contrato Compose estático, 52 enlaces Markdown y la ausencia de source maps
  en el build frontend se verificaron localmente. Prettier también validó la
  documentación operativa.

## Validación pendiente de host real

1. Ejecutar `sudo python3 docker/preflight.py --env-file docker/.env` en Ubuntu.
2. Ejecutar `docker compose --env-file docker/.env up --build --wait -d` y el
   smoke `sh docker/verify-deployment.sh` sobre HTTP local y HTTPS real, más la
   lista visual de navegador para imagen, PDF, audio, vídeo y responsive.
3. Probar renovación de TLS con `certbot renew --dry-run` y recarga de Nginx.
4. Ejecutar el benchmark local de 50 GiB, el benchmark autenticado de despliegue
   con uno y varios clientes, y capturar CPU, RSS, I/O y planes PostgreSQL.
5. Ejecutar un restore drill aislado de PostgreSQL más almacenamiento y guardar
   la evidencia de RPO/RTO.

Estas actividades no se declararon aprobadas porque el entorno de desarrollo
actual no contiene Docker Engine, Docker Compose, Nginx ni un PostgreSQL de
integración. No se inició ninguna fase posterior.
