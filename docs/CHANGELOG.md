# Historial de cambios

Este registro resume cambios que modifican comportamiento, arquitectura,
seguridad u operación. La evidencia detallada pertenece al documento temático
correspondiente.

## 2026-07-20 — Consolidación documental

- La documentación oficial se trasladó y reorganizó bajo `docs/`.
- Arquitectura, decisiones, runbooks, pruebas, seguridad, despliegue y
  reportes históricos se consolidaron por responsabilidad.
- Los Markdown dispersos, ADRs individuales e incrementos históricos fueron
  retirados después de integrar su contenido útil y registrar el mapeo en
  `DOCUMENTATION_AUDIT.md`.
- Se añadió este índice documental, [AGENTS.md](AGENTS.md) y referencias
  internas coherentes.

## 2026-07-20 — Actividad persistente y auditoría frontend

- Se implementaron Recientes y Favoritos de extremo a extremo: migración,
  repositorio, casos de uso, API protegida y páginas React paginadas.
- Inicio pasó a ser la ruta autenticada predeterminada con accesos rápidos,
  estado API y actividad reciente.
- Se corrigieron teclado de filas, semántica ARIA, foco del drawer móvil,
  filtros responsive, imports internos y cache keys duplicadas.
- La migración `20260720_0006` y pruebas de actividad se validaron en la
  candidata.

Evidencia histórica: 178 pruebas frontend, gates de tipo/lint/formato/build/
npm audit y 201 pruebas backend con cobertura de 90,41 % en la candidata.

## 2026-07-20 — Candidata endurecida

- Se añadió worker durable para limpieza de objetos huérfanos mediante outbox
  en dos fases.
- Se añadieron índices para referencias de thumbnails/previews.
- Backup/restore pasó a detener temporalmente rutas de escritura y restaurar
  dump de manera aislada.
- Se retiró `unsafe-inline` de CSP y estilos inline del frontend.
- Secretos de instalaciones nuevas pasan a `/etc/drivempvd`, fuera del checkout.
- Se añadieron preflight, scripts de release/transferencia/runtime, scans y
  smoke compatible con bindings loopback.

Correcciones trazadas en este ciclo:

- Se eliminó la carrera que podía borrar bytes de un objeto compartido.
- Se añadieron índices de referencias de thumbnail/preview.
- Se corrigió el alias duplicado de PostgreSQL en actividad.
- El smoke normaliza bindings privados como `127.0.0.1:18081`.
- El escaneo de imágenes respeta el environment Compose configurado.

## 2026-07-19 — Despliegue, optimización y validación

- Se definieron Compose, Nginx, Dockerfiles, entornos HTTP/TLS y smoke
  autenticado.
- Se añadió buffering de escritura acotado, coalescencia de progreso frontend,
  límites de recursos y herramientas de benchmark.
- Se documentó que `X-Accel-Redirect` sigue preparado pero deshabilitado.

## 2026-07-18 — Base funcional

- Backend modular: Settings, composition root, logging JSON, UoW, PostgreSQL
  async, outbox, autenticación, catálogo, uploads y streaming.
- Frontend React: shell, auth por cookies/CSRF, explorador, uploads, viewers y
  miniaturas acotadas.
- Se eligieron árbol por adyacencia, blobs inmutables opacos, keyset pagination
  y delivery RFC 9110.

### Hitos históricos de incrementos

| Fase | Alcance consolidado |
| --- | --- |
| 2.1 | Settings, composition root, logging JSON, errores, envelope y health. |
| 2.2 | PostgreSQL async, UoW, UUID v7, outbox y readiness. |
| 2.3 | Cuenta singleton, sesiones JWT, cookies, CSRF y lockout. |
| 2.4–2.7 | Storage domain, API de catálogo, uploads y streaming RFC 9110. |
| 3–7 | Base frontend, auth, explorer, uploads y viewers. |
| 8 | Compose/Nginx, entornos y smoke. |
| 9 | Buffers, benchmark y perfil de recursos. |
| 10 | Preflight, restore drill, seguridad y documentación operativa. |

## Cambios futuros

Cada entrada nueva debe incluir:

- fecha;
- alcance y cambio observable;
- riesgo/compatibilidad relevante;
- evidencia de validación;
- enlaces a la documentación temática si el cambio modifica operación.
