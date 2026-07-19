# Frontend de DriveMPVD

SPA React/TypeScript organizada por funcionalidades. La base incluye el shell
responsive, temas, router, caché de datos y un cliente HTTP central compatible
con el envelope del backend.

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
  pages/        Composición de páginas por ruta
  shared/       Cliente API, configuración, UI y utilidades transversales
  styles/       Tokens y estilos globales
  test/         Configuración común de Vitest
```

Los componentes no llaman a `fetch` directamente. Cada feature futura expondrá
una API pública y utilizará `shared/api`; el estado remoto se mantendrá paginado
y nunca contendrá el árbol completo ni bytes de archivos.

## Alcance actual

La Fase 3.1 no incluye login, rutas protegidas, explorador ni transferencias. La
navegación correspondiente aparece deshabilitada deliberadamente hasta que cada
incremento implemente y pruebe su comportamiento real.
