# Nginx

## 1. Responsabilidad

Nginx es el único borde HTTP/HTTPS. Sirve la SPA, proxy `/api` a FastAPI,
termina TLS, aplica límites/rate limits, añade headers de seguridad y conserva
streaming para upload/download.

No monta storage en la composición normal y no entrega blobs directamente.
FastAPI mantiene autorización y semántica HTTP de contenido.

## 2. Rutas

| Ruta | Comportamiento |
| --- | --- |
| `/` | Frontend estático y fallback SPA. |
| `/api` | Proxy hacia API. |
| Upload chunks | `proxy_request_buffering off`, sin temporales de proxy y timeouts largos. |
| Contenido | Sin proxy buffering/caché temporal; conserva Range/ETag. |
| ACME | `/.well-known/acme-challenge/` desde webroot. |
| Internal storage | Reservada para futuro `X-Accel-Redirect`; no pública. |

## 3. Headers y browser security

Nginx debe emitir:

- CSP de mismo origen sin `unsafe-inline`;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: no-referrer`;
- `X-Frame-Options: SAMEORIGIN` y `frame-ancestors 'self'`;
- Permissions Policy restrictiva;
- aislamiento de origen/recurso según configuración;
- HSTS solo en TLS.

Las políticas se prueban en smoke y ZAP. No reemplazar headers de servidor con
metatags del frontend.

## 4. HTTP, HTTPS y certificados

Con `DRIVEMPVD_TLS_ENABLED=true`, Nginx exige `fullchain.pem` y
`privkey.pem` bajo `DRIVEMPVD_TLS_CERTIFICATES_PATH`. El puerto 80 entrega ACME
y redirige el resto a HTTPS.

No montar directamente `/etc/letsencrypt/live/<dominio>` porque sus PEM suelen
ser symlinks. Copiar PEMs dereferenciados a `/etc/drivempvd/tls`, con
`fullchain.pem` 0644 y `privkey.pem` 0600, y recargar Nginx después de renovar.

Ejecutar `certbot renew --dry-run` y comprobar la recarga antes de producción.

## 5. Límites

- `client_max_body_size` inicial de 50 GiB, coherente con backend.
- Rate limits separados para login/refresh, API y contenido.
- Límite de conexiones de contenido por IP.
- Timeouts de upload largos sin buffering para chunks.
- No propagar una cadena `X-Forwarded-For` proporcionada por cliente.

Si se instala proxy/balanceador, definir IPs confiables y modelo real-IP antes
de exponer el servicio.

## 6. Verificación

Validar:

1. `docker compose config --quiet`.
2. Healthcheck Nginx y servicios upstream.
3. Smoke de root, `ready`, login, CSRF, upload, download, `HEAD` y Range.
4. Headers HTTP/HTTPS, cookies y redirección.
5. ACME y renovación en dominio real.
6. Logs sin secrets/query strings y sin errores críticos.

`X-Accel-Redirect` permanece desactivado hasta cumplir [STORAGE.md](STORAGE.md)
y [RELEASE.md](RELEASE.md).
