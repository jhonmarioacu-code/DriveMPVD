# Copias de seguridad, restauración y rollback

## 1. Conjunto consistente

Un backup válido actual incluye:

- dump PostgreSQL;
- árbol completo de `DRIVEMPVD_STORAGE_PATH`, incluyendo `objects` y
  `staging`;
- `SHA256SUMS` de ambos artefactos.

No incluir secretos de producción en backups ordinarios. Gestionarlos con
backup cifrado/gestor de secretos separado.

## 2. Backup y restore drill

```bash
cd /srv/drivempvd
sudo env DRIVEMPVD_COMPOSE_ENV_FILE=/etc/drivempvd/production.env \
  bash docker/verify-backup-restore.sh
```

El procedimiento:

1. toma lock para evitar solapamiento;
2. detiene Nginx, API y worker temporalmente;
3. crea `database.dump` y `storage.tar` bajo `/var/backups/drivempvd`;
4. calcula hashes y reactiva los servicios;
5. restaura dump y storage en recursos desechables;
6. compara la revisión Alembic.

No actualizar ni purgar en paralelo. Conservar salida, hashes, fecha, duración
y resultado.

## 3. Restauración aislada

Nunca restaurar primero sobre producción.

1. Crear environment aislado con project name, path storage, puertos y tag
   distintos.
2. Comprobar `pg_restore --list` y `sha256sum --check`.
3. Extraer storage en ruta vacía aislada.
4. Levantar solo PostgreSQL aislado e importar dump.
5. Levantar restante del stack aislado.
6. Ejecutar smoke, navegación, lectura de objeto existente y subida nueva.
7. Registrar RTO observado, tamaño, revisión y errores.

La recuperación real requiere preservar copia forense del estado presente y
autorización explícita.

## 4. Rollback de release

### Sin migración aplicada

Volver a checkout/tag e imagen anterior y levantar sin rebuild. Ejecutar
health/smoke antes de reabrir servicio.

### Con migración aplicada

No hacer `alembic downgrade`. Restaurar backup coordinado validado y usar una
versión de aplicación compatible con el esquema restaurado. Repetir smoke y
documentar incidente.

## 5. Pendientes

No hay configuración aprobada de destino offsite cifrado, retención, timer,
RPO/RTO o responsable operativo. No declarar recuperabilidad de producción
hasta definirlos y restaurar desde el medio aplicable.

Vea [OPERATIONS.md](OPERATIONS.md) para la rutina y [DATABASE.md](DATABASE.md)
para integridad.
