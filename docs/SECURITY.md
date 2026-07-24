# Seguridad y endurecimiento

## 1. Alcance y postura

DriveMPVD protege un único administrador, sus metadatos y sus archivos. El
modelo prioriza confidencialidad de credenciales, integridad de catálogo/blob,
protección frente a traversal y recuperación operativa.

El sistema no dispone todavía de MFA, recuperación pública de contraseña,
antivirus, pentest externo, escaneo autenticado, worker de medios o
multiusuario. No presentar estas capacidades como existentes.

## 2. Identidad y sesión

| Componente | Responsabilidad |
| --- | --- |
| `AdminAccount` | Singleton lógico, password Argon2id, estado y lockout. |
| `AuthSession` | Familia refresh, HMAC, expiración, CSRF y revocación. |
| `SecurityEvent` | Auditoría append-only con datos pseudonimizados. |
| `AuthRateLimit` | Buckets PostgreSQL atómicos por scope/sujeto. |

Login:

1. Consume bucket `auth.login` pseudonimizado.
2. Lee cuenta con lock y usa hash dummy si no existe.
3. Verifica Argon2id, registra fallos/lockout o éxito.
4. Emite access, refresh y CSRF; la DB solo guarda hashes/HMAC.

Access dura 15 minutos por defecto; refresh 7 días por defecto y rota. La
reutilización de refresh revoca su familia. Cambiar contraseña o revocar todo
invalida sesiones persistidas.

## 3. Transporte, cookies y CSRF

| Cookie | Reglas |
| --- | --- |
| Access | HttpOnly, Secure, SameSite=Lax, path `/`. |
| Refresh | HttpOnly, Secure, SameSite=Strict, path `/api/v1/auth`. |
| CSRF | Secure, SameSite=Lax, legible por SPA y ligada a sesión. |

Toda mutación autenticada por cookie exige cookie CSRF y cabecera homónima
válida. Bearer queda exento porque no depende de cookies. CORS está cerrado:
frontend y API comparten origen.

No almacenar tokens, contraseñas, sesión o usuario en `localStorage` o
`sessionStorage`. JavaScript no debe poder leer access/refresh.

## 4. Rate limit y lockout

Login y refresh usan buckets PostgreSQL con advisory lock transaccional. El
lockout de cuenta se activa tras cinco credenciales fallidas por defecto durante
15 minutos. La respuesta de límite incluye `429` y `Retry-After`.

No introducir un proxy externo sin configurar origen real, IPs confiables y
límites por cliente.

## 5. Validación de entradas y archivos

- Nombres Unicode normalizados, longitud acotada, sin NUL, separadores,
  `.`, `..` o controles.
- Rutas lógicas por segmentos validados.
- Keys opacas generadas por servidor; jamás paths del cliente.
- Límites de body, chunk, headers, metadata y tamaño total.
- MIME detectado por servidor; extensión no concede seguridad.
- HTML/SVG/contenido activo no se entrega inline.
- Archivos comprimidos no se extraen.
- No se siguen symlinks externos fuera de la raíz permitida.

## 6. Borde y navegador

Nginx debe emitir CSP de mismo origen sin `unsafe-inline` para scripts/estilos,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
`X-Frame-Options: SAMEORIGIN`, `frame-ancestors 'self'` y políticas
restrictivas de permisos/aislamiento.

HSTS se emite solo por TLS. `SAMEORIGIN` permite PDF inline autenticado sin
autorizar embedding de terceros.

## 7. Contenedores y host

- API, frontend y worker usan usuario no privilegiado y filesystem readonly.
- Capacidades se eliminan salvo necesidad mínima de Nginx.
- PostgreSQL está en red interna y no publica puerto.
- Storage se monta solo en API/worker.
- Nginx es el único servicio con puertos publicados.
- Entornos de producción residen en `/etc/drivempvd` con modo `0600`.
- Certificados no viven en Git, imagen ni checkout.

El firewall de la candidata documentada usaba `deny incoming` con SSH, 80 y
443 como excepciones. Verificar configuración real antes de declararla vigente.

## 8. Gates de seguridad

| Gate | Comando |
| --- | --- |
| Fuente/misconfiguración | `sudo bash docker/verify-source-security.sh` |
| Imágenes | `sudo bash docker/verify-container-images.sh` |
| Backend/dependencias | `sudo sh docker/verify-postgresql-tests.sh` |
| Frontend/dependencias | `sudo sh docker/verify-frontend.sh` |
| Navegador | `docker/verify-zap-baseline.sh` en entorno autorizado |

Los scanners cubren lo configurado; un resultado limpio no equivale a ausencia
absoluta de vulnerabilidades. Revisar además secretos, headers, ACL de archivos,
DNS/TLS, logs y rutas publicadas.

## 9. Pendientes de seguridad

- Dominio y certificado público aún no validados.
- No hay pentest externo ni scan autenticado.
- No hay MFA ni recuperación automática.
- Rotar secretos invalida sesiones; no existe rotación solapada con `kid`.
- No existe alertado/retención/exportación SIEM de eventos.
- Antivirus, procesamiento de medios y limpieza de staging siguen pendientes.

Para despliegue seguro, consulte [NGINX.md](NGINX.md), [VPS.md](VPS.md) y
[RELEASE.md](RELEASE.md).
