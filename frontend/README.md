# Frontend de DriveMPVD

SPA React/TypeScript organizada por funcionalidades. Incluye shell responsive,
temas, autenticación por cookies, rutas protegidas, caché de datos y un cliente
HTTP central compatible con el envelope del backend.

## Requisitos

- Node.js 22.12 o superior.
- npm 10 o superior.
- Backend disponible en `http://127.0.0.1:8000` para comprobar la integración.

## Desarrollo

```powershell
npm ci
npm run dev
```

Vite sirve la aplicación en `http://localhost:5173` y redirige `/api` al backend
local. `VITE_API_BASE_URL` permite cambiar la base de la API; su valor por
defecto es `/api/v1` para conservar mismo origen y cookies.

## Verificación

```powershell
npm run format
npm run lint
npm run typecheck
npm test
npm run build
```

Las pruebas exigen al menos 80 % de líneas, sentencias, funciones y ramas.

## Estructura

```text
src/
  app/          Providers, router y shell de aplicación
  features/     Funcionalidades aisladas: auth y explorer
  pages/        Composición de páginas por ruta
  shared/       Cliente API, configuración, UI y utilidades transversales
  styles/       Tokens y estilos globales
  test/         Configuración común de Vitest
```

Los componentes no llaman a `fetch` directamente. Cada feature expone una API
pública y utiliza `shared/api`; el estado remoto se mantendrá paginado y nunca
contendrá el árbol completo ni bytes de archivos.

## Autenticación local

El frontend usa cookies del backend y no almacena JWT, contraseña ni usuario en
`localStorage`. Para desarrollo HTTP, configura
`DRIVEMPVD_AUTH_COOKIE_SECURE=false` en el backend si el navegador no admite la
excepción segura de `localhost`; producción siempre debe utilizar HTTPS y
cookies `Secure`.

## Explorador

La ruta privada predeterminada es `/files`. Resuelve la raíz canónica mediante
`GET /storage/navigation`, conserva en TanStack Query las rutas y páginas por
cursor, y permite navegar carpetas, filtrar, ordenar, seleccionar y ejecutar
crear carpeta, renombrar, mover, enviar a papelera, abrir y descargar. Las
descargas usan una URL autenticada del backend y no cargan bytes del archivo en
memoria del navegador.

Subidas, visualizadores y miniaturas pertenecen a fases posteriores.
