# ADR-0004: JWT en cookies y protección CSRF

- Estado: aceptada
- Fecha: 2026-07-18

## Contexto

La SPA y API comparten origen. Guardar tokens en JavaScript aumenta el impacto
de XSS; usar cookies introduce riesgo CSRF.

## Decisión

Usar access JWT corto en cookie HttpOnly y refresh opaco rotatorio cuyo hash se
persiste. Exigir token CSRF y validación de origen en mutaciones. Mantener CORS
cerrado por defecto y aplicar CSP estricta.

## Consecuencias

JavaScript no puede leer credenciales, hay revocación efectiva de refresh y la
API sigue autenticando con JWT. El cliente debe obtener/enviar CSRF y el backend
debe gestionar rotación y detección de reutilización correctamente.
