# Autenticación y modelo de amenazas

## Alcance

Existe exactamente un administrador. PostgreSQL impide una segunda fila
mediante `singleton_key = TRUE` único. No existen registro, roles, permisos,
invitaciones ni recuperación pública. La cuenta inicial se crea por CLI.

## Componentes

| Componente | Responsabilidad |
|---|---|
| `AdminAccount` | Hash Argon2id, estado, fallos y lockout temporal |
| `AuthSession` | Familia refresh, HMAC vigente, CSRF, expiración y revocación |
| `SecurityEvent` | Auditoría append-only con IP/user-agent pseudonimizados |
| `AuthRateLimit` | Buckets PostgreSQL atómicos por scope/sujeto |
| Middleware | Extraer Bearer/cookie y delegar en `AuthenticateAccessUseCase` |

Dominio y aplicación no importan FastAPI, SQLAlchemy, PyJWT ni Argon2. El
composition root inyecta puertos de criptografía, repositorios, reloj e ids.

## Login

1. Se consume el bucket `auth.login`, pseudonimizado con HMAC.
2. La cuenta se lee con lock; un username inexistente ejecuta un hash dummy.
3. Argon2id verifica. Los errores públicos no revelan si existe la cuenta.
4. Los fallos se confirman junto con contador, lockout y evento de seguridad.
5. El éxito limpia fallos, hace rehash si cambió la política y crea sesión.
6. Access/refresh JWT y CSRF se emiten; solo HMAC de refresh/CSRF llega a DB.

## Tokens

Claims comunes: `iss`, `aud`, `sub`, `sid`, `jti`, `type`, `iat`, `nbf`, `exp`.
Refresh añade `fid`. El algoritmo está fijado a HS256 y access/refresh usan
secretos diferentes. No se acepta el algoritmo anunciado sin allowlist.

- Access: 15 minutos por defecto; cada uso verifica sesión y cuenta.
- Refresh: 7 días por defecto, expiración absoluta; rota token, `jti` y CSRF.
- Logout/revoke-all: revocación persistente inmediata.
- Reuse: un refresh válido criptográficamente pero distinto del vigente revoca
  la familia y registra `auth.refresh_reuse_detected`.

## Transporte

Cookie principal:

- access: HttpOnly, Secure, SameSite=Lax, path `/`;
- refresh: HttpOnly, Secure, SameSite=Strict, path `/api/v1/auth`;
- CSRF: Secure, SameSite=Lax, legible por SPA, sin credenciales.

Login/refresh aceptan `delivery=bearer` para clientes no navegador. En ese modo
los tokens se devuelven en el envelope y el access se envía con
`Authorization: Bearer`. Si hay Bearer y cookie, Bearer tiene precedencia.

## CSRF

Para mutaciones con access cookie, middleware exige cookie y cabecera CSRF; las
dos deben coincidir con el HMAC de sesión. Refresh valida el mismo mecanismo con
la refresh cookie. Bearer no depende de cookies y queda exento. CORS permanece
cerrado y `Origin` será reforzado junto con las cabeceras/Nginx de despliegue.

## Rate limiting y bloqueo

Login y refresh usan buckets PostgreSQL. Un advisory lock transaccional por
sujeto hace atómico el incremento entre procesos. Al exceder el límite se
responde `429` y `Retry-After`. El lockout de cuenta es independiente y se
activa tras cinco credenciales fallidas por defecto durante 15 minutos.

## Eventos

Se conservan creación del administrador, login correcto/fallido, rotación,
reutilización, logout y revocación total. No se registran passwords, JWT, CSRF,
IP o user-agent en claro. Los detalles son cerrados y no contienen secretos.

## Modelo de amenazas

| Amenaza | Mitigación | Riesgo residual |
|---|---|---|
| Credential stuffing | Argon2id, rate limit y lockout | DoS dirigido al singleton |
| Enumeración | Error uniforme y verificación dummy | Diferencias externas de red |
| Robo por XSS | Credenciales HttpOnly y CSP prevista | XSS puede actuar como usuario |
| CSRF | SameSite, doble submit ligado a sesión | Requiere proteger el origen |
| Robo refresh | Rotación y detección de reuse | El atacante que rota primero causa revocación |
| Access robado | TTL corto y consulta de revocación | Válido hasta revocar/detectar |
| Fuerza bruta JWT | Secretos >=32 bytes, algoritmo fijo | Custodia/rotación de secretos |
| Abuso distribuido | Cuenta lock + bucket por IP/usuario | PostgreSQL no sustituye WAF/Nginx |
| DB comprometida | Password Argon2 y tokens con HMAC | Sesiones/metadatos quedan expuestos |

## Limitaciones

- No hay MFA ni recuperación automática; una recuperación es operación local.
- No hay rotación solapada de claves (`kid`); cambiar secreto invalida sesiones.
- La confianza en IP depende de configurar correctamente proxies de Uvicorn/Nginx.
- Los eventos aún no tienen retención/alertas ni exportación SIEM.
- Multiusuario/RBAC exige migración explícita; no hay permisos latentes o falsos.
