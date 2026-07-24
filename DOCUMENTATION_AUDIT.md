# Auditoría de documentación — DriveMPVD

## Resultado ejecutivo

La documentación se reorganizó en una única estructura oficial bajo `docs/`.
Se analizaron **67 archivos Markdown propios** del repositorio, excluyendo
documentación de dependencias instaladas. Se retiraron **62 rutas Markdown
heredadas** después de consolidar su contenido útil; cinco documentos existentes
se reescribieron y normalizaron por capitalización para formar parte del
conjunto oficial.

La estructura oficial contiene 18 documentos:

```text
docs/
  AGENTS.md          README.md          ARCHITECTURE.md
  DEVELOPMENT.md     API.md             DATABASE.md
  STORAGE.md         SECURITY.md        TESTING.md
  DEPLOYMENT.md      VPS.md             DOCKER.md
  NGINX.md           BACKUP.md          OPERATIONS.md
  TROUBLESHOOTING.md CHANGELOG.md       RELEASE.md
```

## Alcance y método

1. Se inventariaron todos los `*.md` propios con sus tamaños, headings y enlaces.
2. Se leyó el contenido técnico, histórico y operativo de cada familia.
3. Se localizaron referencias Markdown y se comprobó que código, React,
   FastAPI, Docker, Nginx, PostgreSQL y scripts no dependían de los nombres
   antiguos.
4. Se clasificó cada documento como canónico, fusionable, histórico o
   obsoleto por estructura.
5. Se integró la información de producto, arquitectura, decisiones, pruebas,
   seguridad, operación, riesgos e históricos en la documentación oficial.
6. Se validaron los 18 documentos oficiales y sus enlaces relativos.

## Documentos analizados

| Grupo | Rutas analizadas | Tratamiento |
| --- | --- | --- |
| Resúmenes raíz | `README.md`, `ARCHITECTURE.md`, `INSTALL.md`, `DEPLOY.md`, `BACKUP.md`, `RESTORE.md`, `MAINTENANCE.md` | Fusionados por tema en `docs/`. |
| Informes raíz | `AUDIT_REPORT.md`, `DEPLOY_REPORT.md`, `SECURITY_REPORT.md`, `SYNC_REPORT.md`, `TEST_REPORT.md`, `FIXES.md`, `KNOWN_ISSUES.md` | Evidencia histórica, correcciones y pendientes integrados en Testing, Security, Operations, Release y Changelog. |
| Historial raíz | `CHANGELOG.md` | Consolidado en `docs/CHANGELOG.md`. |
| Backend | `backend/README.md` y READMEs de `domain`, `application`, `infrastructure`, `presentation` y `shared` | Límites y desarrollo integrados en Architecture, Development, Database y Storage. |
| Frontend | `frontend/README.md` y `docs/frontend-architecture.md` | Arquitectura frontend, rutas, UX, uploads y viewers integrados en Architecture, Development, API, Storage y Testing. |
| Docker/scripts | `docker/README.md` y `scripts/README.md` | Integrados en Docker, Deployment, VPS, Nginx y Release. |
| Documentos técnicos `docs/` | `architecture.md`, `api.md`, `authentication.md`, `domain-model.md`, `storage.md`, `storage-domain.md`, `security.md`, `testing-strategy.md`, `performance.md`, `operations.md`, `maintenance.md`, `requirements-traceability.md` | Reorganizados por responsabilidad en los 18 documentos oficiales. |
| ADRs | `docs/adr/README.md` y ADR-0001 a ADR-0013 | Decisiones, consecuencias y reemplazos consolidados en Architecture, Security, Database y Storage. |
| Incrementos | `docs/increments/README.md` y fases 2.1–2.7, 3.1, 4–10 | Hitos, evidencia y limitaciones preservados en Changelog, Testing, Development, Deployment y Release. |

## Consolidación por destino

| Destino oficial | Fuentes consolidadas | Información preservada |
| --- | --- | --- |
| `docs/AGENTS.md` | Instrucciones dispersas, runbooks y límites | Protocolo de agentes, autorización, gates y definición de terminado. |
| `docs/README.md` | README raíz y mapas documentales | Introducción, estado de referencia e índice general. |
| `docs/ARCHITECTURE.md` | Architecture raíz, arquitectura, ADRs, frontend architecture y trazabilidad | Monolito modular, capas, decisiones, módulos, frontend y estado funcional. |
| `docs/DEVELOPMENT.md` | Backend/frontend READMEs, convenciones y CI | Setup, estilo, migraciones, validación y documentación de cambios. |
| `docs/API.md` | API REST, fases de auth/storage/activity | Convenciones, recursos, auth, uploads, activity, delivery y compatibilidad. |
| `docs/DATABASE.md` | Domain model, storage domain, persistencia y ADRs DB | Modelo, invariantes, índices, UoW, migraciones, outbox e integridad. |
| `docs/STORAGE.md` | Storage, storage domain, fases 2.6/2.7/6/7 | Layout, provider, upload, download, Range, preview, thumbnails y limpieza. |
| `docs/SECURITY.md` | Security, authentication, ADR auth y security report | Sesiones, CSRF, headers, host, scans y pendientes. |
| `docs/TESTING.md` | Testing strategy, reportes, fases y CI | Pirámide, gates, smoke, benchmarks, resultados y pendientes. |
| `docs/DEPLOYMENT.md` | Install, deploy, operations, scripts | Vías soportadas, candidata, preflight, deploy y validación posterior. |
| `docs/VPS.md` | Operations, deploy report e install-vps | Ubuntu, almacenamiento, firewall, secretos, recursos y acceso privado. |
| `docs/DOCKER.md` | Compose, Docker README y fases de deploy | Servicios, redes, entornos, operación y overlay accel. |
| `docs/NGINX.md` | Nginx config, security, operations y Docker README | Rutas, TLS, headers, streaming, límites y verificación. |
| `docs/BACKUP.md` | Backup, restore, maintenance y runbooks | Snapshot coordinado, drill, recuperación y rollback. |
| `docs/OPERATIONS.md` | Maintenance, audit/deploy reports y known issues | Rutina, observabilidad, incidentes y riesgos. |
| `docs/TROUBLESHOOTING.md` | Fixes, reports y fallos documentados | Síntomas, diagnóstico, recuperación y escalamiento. |
| `docs/CHANGELOG.md` | Changelog, incrementos, fixes y auditoría | Hitos históricos, correcciones y reglas de entradas futuras. |
| `docs/RELEASE.md` | Sync, deploy, scripts, reports y known issues | Git, manifiestos, transferencia, RC, producción y gates. |

## Documentos retirados y motivo

Los siguientes grupos se eliminaron porque su contenido fue consolidado y
mantenerlos crearía información duplicada o dispersa:

- 15 resúmenes, reportes y runbooks de la raíz.
- 9 READMEs locales de backend, frontend, Docker y scripts.
- 8 documentos técnicos temáticos antiguos bajo `docs/`.
- 14 ADRs individuales y su índice: las decisiones aceptadas se preservaron
  como registro consolidado de arquitectura; futuras decisiones se documentan
  en `docs/ARCHITECTURE.md` y changelog hasta que se apruebe otro formato.
- 16 documentos de incrementos/fases: su evidencia histórica se preservó en
  `docs/CHANGELOG.md` y `docs/TESTING.md`; no eran el estado operativo vigente.

No se eliminó ninguna capacidad, riesgo, limitación, procedimiento de
recuperación ni resultado histórico sin trasladarlo a un documento temático o
registrarlo como pendiente.

## Enlaces corregidos

- Los enlaces de `docs/architecture.md`, `api.md`, `security.md`,
  `storage.md` y `operations.md` se reemplazaron por enlaces de capitalización
  uniforme en los documentos oficiales.
- Se eliminó la dependencia de rutas raíz y subdirectorios `adr/` e
  `increments/`.
- Los enlaces internos de los 18 documentos oficiales se validaron con
  resultado: **0 enlaces relativos rotos**.

## Validación posterior a la consolidación

| Control | Resultado | Alcance |
| --- | --- | --- |
| Estructura oficial | Conforme | 18 de 18 archivos requeridos en `docs/`; sin archivos Markdown temáticos adicionales. |
| Navegación interna | Conforme | Cada documento oficial contiene al menos una referencia a documentación relacionada; el índice enlaza los 18. |
| Enlaces locales | Conforme | 0 enlaces Markdown relativos rotos en la documentación activa y los dos informes de auditoría. |
| Duplicación literal | Conforme | No hay párrafos no generados de 100 o más caracteres repetidos exactamente entre documentos oficiales. |
| Rutas retiradas | Conforme | No hay referencias a nombres heredados en documentación activa, código, React, FastAPI, Compose, Nginx, PostgreSQL, scripts ni CI. |
| Contraste con el árbol | Conforme con pendientes conocidos | Se revisaron rutas FastAPI, paquetes, migraciones, `compose.yaml`, Nginx, scripts de runtime y gates de CI. Las referencias documentales a rutas estáticas existen; `docker/.env` es la excepción esperada porque se genera desde su plantilla. Los límites no completados permanecen declarados como pendientes, no como capacidades certificadas. |

## Pendientes detectados

- Git local/remoto/tag inmutable siguen pendientes de certificación.
- Dominio, DNS, TLS público, HSTS y exposición autorizada no están cerrados.
- No existe backup offsite cifrado, retención, RPO/RTO ni timer.
- Faltan 50 GiB, concurrencia, tráfico Internet y E2E/browser real.
- Papelera frontend, limpieza de staging, DLQ/backoff/retención de outbox y
  worker de medios continúan pendientes.

## Recomendaciones de mantenimiento

1. Crear/editar documentación solo en `docs/` y actualizar el documento del
   tema propietario, no duplicar texto.
2. Mantener `CHANGELOG.md` para hitos y `RELEASE.md` para gates; no crear
   reportes permanentes en la raíz sin motivo.
3. En cada cambio, validar enlaces relativos y revisar `docs/AGENTS.md`.
4. Registrar evidencia fechada, no copiar resultados de pruebas antiguas.
5. Si se adopta nuevamente un formato ADR individual, definirlo formalmente y
   enlazarlo desde Architecture sin fragmentar los runbooks.

## Limitación importante

Esta reorganización cambia el árbol de archivos fuente. Cualquier digest de
sincronización Local–VPS previo queda históricamente válido solo para la versión
anterior; antes de un despliegue se debe generar una comparación SHA-256 nueva.
