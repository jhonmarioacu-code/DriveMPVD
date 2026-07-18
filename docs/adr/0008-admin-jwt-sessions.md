# ADR-0008: Sesiones JWT rotatorias del administrador

- Estado: aceptada
- Fecha: 2026-07-18

## Contexto

La aplicación requiere una sola cuenta, cookies como transporte principal,
clientes Bearer futuros, revocación inmediata y defensa contra replay de
refresh tokens, sin introducir roles o un proveedor externo.

## Decisión

Esta decisión reemplaza únicamente el refresh opaco previsto en ADR-0004; se
mantienen cookies HttpOnly y CSRF.

Persistir un singleton `AdminAccount` y una fila `AuthSession` por dispositivo.
Emitir access JWT corto y refresh JWT con secretos y validaciones independientes.
El access contiene `session_id` y cada petición autenticada confirma que la
sesión sigue activa. La sesión guarda solo el HMAC del refresh vigente y el
`jti`; la rotación ocurre bajo `SELECT FOR UPDATE`. Un token anterior revoca la
familia.

Cookies HttpOnly/Secure/SameSite son el transporte predeterminado. Las
mutaciones autenticadas por cookie requieren cookie CSRF no HttpOnly, cabecera
homónima y coincidencia con el HMAC almacenado. Bearer no usa CSRF. Argon2id,
rate limits PostgreSQL y lockout temporal protegen credenciales.

## Consecuencias

La revocación es inmediata pero añade una lectura indexada por petición. HS256
simplifica el único servidor; rotar sus secretos invalida tokens activos. El
singleton y ausencia de roles son restricciones deliberadas. Multiusuario
requerirá una migración que retire `singleton_key`, añada políticas y cambie
los nombres de puertos, sin modificar los adaptadores criptográficos.
