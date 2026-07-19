# Fase 3.1: base del frontend

- Estado: implementado y validado
- Fecha: 2026-07-18

## Alcance

- Proyecto reproducible con React 19, TypeScript estricto, Vite y lock de npm.
- Tailwind CSS con tokens semánticos para temas claro, oscuro y del sistema.
- Shell responsive con navegación lateral, drawer móvil, cabecera y ruta 404.
- Proveedores aislados para router, temas y caché de TanStack Query.
- Cliente HTTP central con cookies, cancelación, configuración por entorno y
  validación del envelope `data/error/meta` de la API existente.
- Comprobación funcional de `/api/v1/health` con carga, éxito, error correlacionado
  por `request_id` y reintento manual.
- Fundamentos accesibles: skip link, foco visible, nombres accesibles, teclado,
  contraste semántico y respeto por reducción de movimiento.
- ESLint con reglas tipadas, Prettier, Vitest, Testing Library, cobertura y build
  de producción como puertas obligatorias.

No se modificó el backend. Login, renovación de sesión, CSRF, rutas protegidas,
explorador, notificaciones y transferencias quedan fuera de este incremento.

## Decisiones

El frontend usa mismo origen por defecto y Vite redirige `/api` al backend local.
Esto conserva el modelo de cookies HttpOnly sin introducir CORS como requisito.
El cliente HTTP es la única frontera de red y ya usa `credentials: include`; la
inyección de CSRF y la renovación serializada se añadirán junto con autenticación.

La navegación futura permanece visible pero deshabilitada para validar el layout
sin prometer funciones inexistentes. El shell coordina páginas y providers, pero
no importa internals de features futuras.

## Validación

Validado localmente con Node.js 24.18.0 y npm 11.16.0:

| Control                | Resultado                               |
| ---------------------- | --------------------------------------- |
| Prettier               | Sin diferencias                         |
| ESLint                 | Sin incidencias ni advertencias         |
| TypeScript estricto    | Proyectos app y Node sin incidencias    |
| Vitest                 | 16 pruebas superadas                    |
| Cobertura líneas/ramas | 96,58 % / 90,10 %; mínimo 80 %          |
| Build Vite             | Correcto; JS 367,61 kB (117,70 kB gzip) |

Las pruebas cubren contrato HTTP, errores uniformes, credenciales, respuesta
inválida, temas persistidos y del sistema, shell móvil, 404 y los estados de la
conexión con la API.

## Siguiente incremento

La siguiente etapa es login e integración de autenticación. Debe implementar el
estado de sesión y las rutas públicas/protegidas sobre los endpoints existentes,
sin iniciar todavía el explorador.
