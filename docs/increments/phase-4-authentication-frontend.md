# Fase 4: login, integración de autenticación y endurecimiento

- Estado: implementado y validado
- Fecha: 2026-07-18

## Alcance

- Pantalla de acceso responsive, accesible y sin registro público.
- Estado global de sesión y administrador mantenido solo en memoria.
- Login por `delivery=cookie` contra `/api/v1/auth/login`.
- Recuperación de la identidad mediante `/api/v1/auth/session`.
- Rutas privadas y públicas con carga inicial, redirección y conservación segura
  del destino solicitado.
- Cierre de sesión contra `/api/v1/auth/logout`, limpieza del estado y de toda la
  caché remota.
- Renovación de access cookie contra `/api/v1/auth/refresh`, serializada para
  impedir solicitudes concurrentes y repetición única de la petición original.
- Expiración o revocación de sesión traducida a estado no autenticado y retorno
  automático al login.
- CSRF leído exclusivamente desde la cookie pública configurada e incorporado a
  métodos mutables mediante `X-CSRF-Token`.
- Errores públicos para credenciales inválidas, cuenta deshabilitada, rate limit,
  configuración de cookies y fallos de red; `Retry-After` se conserva.

## Seguridad

El navegador nunca recibe JWT desde JavaScript porque el frontend solicita
entrega por cookies. Access y refresh siguen siendo HttpOnly y solo el valor CSRF
se lee al enviar una mutación. Tokens, contraseña, usuario y sesión no se guardan
en `localStorage` ni `sessionStorage`.

Todas las llamadas usan `credentials: include`, mismo origen y `cache: no-store`
en endpoints de autenticación. El documento aplica `Referrer-Policy: no-referrer`
mediante meta para el cliente estático. CSP, HSTS, `frame-ancestors`,
`nosniff` y Permissions Policy deben emitirse como cabeceras de Nginx en la fase
de despliegue; no se simulan desde JavaScript.

## Compatibilidad con el backend

No fue necesario modificar el backend. El cliente añadió una operación explícita
para envelopes exitosos con `data: null`, requerida por logout. Los nombres de
cookie y cabecera CSRF son configurables mediante `VITE_CSRF_COOKIE_NAME` y
`VITE_CSRF_HEADER_NAME`, con los valores vigentes del backend como predeterminados.

En desarrollo HTTP puede requerirse `DRIVEMPVD_AUTH_COOKIE_SECURE=false`. En
producción debe conservarse `true` y servirse exclusivamente mediante HTTPS.

## Validación

Validado localmente con Node.js 24.18.0 y npm 11.16.0:

| Control                | Resultado                               |
| ---------------------- | --------------------------------------- |
| Prettier               | Sin diferencias                         |
| ESLint                 | Sin incidencias ni advertencias         |
| TypeScript estricto    | Proyectos app y Node sin incidencias    |
| Vitest                 | 33 pruebas superadas                    |
| Cobertura líneas/ramas | 92,70 % / 81,46 %; mínimo 80 %          |
| Build Vite             | Correcto; JS 379,08 kB (121,15 kB gzip) |

Las pruebas cubren login, logout, rutas públicas/privadas, destino original,
estados de carga y error, cookies CSRF, errores uniformes, rate limit, respuesta
sin datos, renovación única y serialización de refresh concurrente.

## Incidencias resueltas

- El logout del backend retorna correctamente un envelope con `data: null`; el
  cliente anterior interpretaba cualquier dato nulo como contrato inválido.
- La primera redirección tras login podía competir con el guard público. El guard
  es ahora la única autoridad que restaura y valida destinos internos.
- Las pruebas detectaron y corrigieron reutilización de objetos `Response` ya
  consumidos; no correspondía a un defecto del runtime.

## Siguiente fase

La Fase 5 corresponde al explorador de archivos. No se inició ningún componente,
consulta ni ruta de esa fase.
