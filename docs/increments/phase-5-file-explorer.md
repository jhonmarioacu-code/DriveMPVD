# Fase 5: explorador de archivos

- Estado: implementado y validado
- Fecha: 2026-07-18

## Alcance entregado

- Ruta privada predeterminada `/files` integrada en el shell responsive y en el
  estado de autenticación de la Fase 4.
- Explorador de raíz y carpetas con breadcrumbs, navegación por doble clic,
  teclado y enlaces de ruta.
- Listado paginado por cursor con TanStack Query, filtro por nombre, orden por
  nombre/fecha/tamaño/tipo, cambio de dirección y carga de páginas adicionales.
- Selección individual o de todos los elementos visibles, con acciones
  contextuales habilitadas según tipo y cantidad seleccionada.
- Crear carpetas, renombrar, mover y enviar a papelera usando los endpoints
  existentes; cada mutación invalida la caché del explorador.
- Detalle de archivos, apertura en una pestaña nueva y descarga directa sin
  cargar bytes de contenido en memoria JavaScript.
- Estados accesibles de carga, carpeta vacía, filtros sin resultados, permisos,
  errores recuperables y diálogos de confirmación.
- Iconografía para carpetas, imágenes, audio, vídeo, archivos, documentos,
  hojas de cálculo, presentaciones y comprimidos.

## Compatibilidad con el backend

Se realizó la mínima ampliación necesaria para que el frontend no tuviera que
adivinar la raíz ni reconstruir ancestros:

- El bootstrap del administrador crea la raíz canónica `Drive` en la misma
  transacción.
- La migración `20260718_0004` crea la raíz para administradores existentes que
  no la tengan; el downgrade no elimina datos de usuario.
- `GET /api/v1/storage/navigation` resuelve la raíz o una carpeta y retorna el
  breadcrumb autorizado desde la raíz.

No se modificaron contratos de carga ni streaming. Las mutaciones conservan el
CSRF, cookies y reintento de sesión centralizados en el cliente HTTP de la
Fase 4.

## Estructura relevante

```text
frontend/src/features/explorer/
  api/        Adaptador de endpoints de almacenamiento
  model/      Tipos, queries TanStack, formatos y acciones de archivo
  ui/         Página, filas, iconos y diálogos accesibles
backend/
  alembic/    Revisión 20260718_0004 de aprovisionamiento de raíz
  app/...     Query de navegación y adaptador HTTP correspondiente
```

## Validación

| Control                               | Resultado                                      |
| ------------------------------------- | ---------------------------------------------- |
| Prettier                              | Sin diferencias                                |
| ESLint                                | Sin incidencias ni advertencias                |
| TypeScript estricto                   | Correcto                                       |
| Vitest                                | 53 pruebas superadas                           |
| Cobertura frontend                    | 91,07 % sentencias; 80,57 % ramas; mínimo 80 % |
| Build Vite                            | Correcto; JS 407,62 kB (128,27 kB gzip)        |
| Backend Black/Ruff/MyPy               | Correcto                                       |
| Backend Pytest sin PostgreSQL externo | 80 superadas, 26 omitidas                      |

Las pruebas cubren rutas, caché y paginación, breadcrumbs, selección, diálogos,
mutaciones, estados de error y permisos, iconos, acciones de apertura/descarga,
contrato HTTP y provisión/navegación de la raíz.

## Incidencias resueltas

- El backend no tenía una forma segura de descubrir la raíz del propietario ni
  de construir breadcrumbs para una carpeta arbitraria. Se resolvió con una
  consulta de ruta acotada por propietario y el endpoint de navegación.
- Las cuentas creadas antes del explorador podían no tener raíz. La migración de
  datos las completa sin reescribir ni borrar entradas existentes.
- La máquina de validación no tenía `DRIVEMPVD_TEST_DATABASE_URL`; por ello las
  26 pruebas de integración PostgreSQL quedaron omitidas y el perfil completo
  de cobertura del backend no puede alcanzar su mínimo del 90 % en este entorno
  (62,15 % al ejecutarlo). El perfil sin cobertura pasó y la revisión Alembic
  quedó reconocida como `20260718_0004 (head)`; la puerta de cobertura completa
  debe ejecutarse contra PostgreSQL 16 antes del despliegue.

## Siguiente fase

La Fase 6, subidas normales y reanudables, sigue pendiente y no se inició.
