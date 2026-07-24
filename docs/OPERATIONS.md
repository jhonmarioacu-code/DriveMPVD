# Operación y mantenimiento

## 1. Estado operativo de referencia

La documentación histórica registra una candidata privada en Ubuntu 24.04 con
PostgreSQL, API, worker, frontend y Nginx sanos; smoke autenticado, restore
drill, scans y benchmark loopback de 256 MiB aprobados. No equivale a
producción pública.

La última evidencia de candidata describió listeners web exclusivamente en
loopback, incluido HTTP `127.0.0.1:18081` y HTTPS `127.0.0.1:18444`. Es una
referencia histórica; inspeccionar listeners actuales antes de comunicar una
URL o abrir firewall.

Verificar el estado real mediante healthchecks, logs, versión, hashes y
[RELEASE.md](RELEASE.md) antes de usar esta evidencia.

## 2. Rutina

| Frecuencia | Acción |
| --- | --- |
| Por release | Backup, preflight, deploy gate, scans, smoke, logs, changelog y evidencia. |
| Periódica | `docker compose ps`, healthchecks, logs, disco, inodos, CPU/RSS/I/O y outbox. |
| Periódica | Verificar backups, hashes y restore drill. |
| Antes de vencimiento | `certbot renew --dry-run` y recarga Nginx. |
| Según política pendiente | Dependencias, permisos, firewall, acceso SSH y secret rotation. |

No existe todavía timer de backup, réplica offsite, retención automática ni
alertado formal. Marcarlo como pendiente, no como proceso operativo existente.

## 3. Observabilidad

Los logs son JSON a stdout y deben incluir `request_id`, caso de uso, duración
y resultado, sin secretos ni nombres sensibles completos.

Revisar:

- `Traceback`, `CRITICAL`, `FATAL`, `Unhandled exception` y `panic`;
- healthchecks de PostgreSQL/API/worker/frontend/Nginx;
- heartbeat del worker;
- backlog/errores/intententos de outbox;
- crecimiento de staging y storage;
- memoria, CPU, disco, inodos y carga de DB;
- cambios de puerto/listeners/firewall.

## 4. Mantenimiento permitido

- Aplicar actualizaciones mediante release verificable, no cambios manuales en
  contenedor.
- Rotar contraseña administrativa con `docker/rotate-admin-password.sh` sin
  pasar password en argumentos.
- Mantener certificados y permisos.
- Ejecutar backup/restore drill bajo ventana autorizada.
- Revisar espacio antes de upload grande, backup o benchmark.

No borrar staging, sesiones expiradas, previews o blobs manualmente. El worker
actual solo limpia objetos huérfanos posteriores a purga.

## 5. Incidentes

1. Contener el impacto si está autorizado.
2. Preservar logs, estado, hashes, versiones y timestamps.
3. No borrar evidencia ni reiniciar a ciegas.
4. Clasificar: seguridad, disponibilidad, integridad, datos, rendimiento o UX.
5. Reproducir en entorno aislado si es posible.
6. Corregir causa raíz, añadir regresión y ejecutar gates.
7. Registrar cronología, impacto, recuperación y prevención.

Para discrepancias DB/storage, detener purgas, preservar evidencia y consultar
[STORAGE.md](STORAGE.md) y [BACKUP.md](BACKUP.md).

## 6. Riesgos abiertos

- Papelera frontend incompleta.
- Sin limpieza automática de staging/sesiones/derivados.
- Sin DLQ/backoff/retención de outbox.
- Sin offsite/retención/RPO/RTO.
- Sin TLS/DNS público ni validación Internet.
- Sin benchmark 50 GiB/concurrencia.
- Sin E2E navegador/validación visual completa.
- Sin trazabilidad Git remota certificada.
