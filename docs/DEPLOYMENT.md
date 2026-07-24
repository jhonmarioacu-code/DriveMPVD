# Despliegue paso a paso

## 1. Vías admitidas

Para producción pública, la vía soportada es un release verificable desde Git:
tag inmutable, SHA resuelto, checkout/artefacto limpio y manifiesto de release.
Consulte [RELEASE.md](RELEASE.md).

`rsync`, SCP y SFTP son transporte alternativo hacia
`/srv/drivempvd/releases`. Depositan un artefacto con hashes; no deben
sobrescribir el checkout activo ni iniciar servicios por sí mismos. FTP está
prohibido.

## 2. Precondiciones

- Host Ubuntu preparado según [VPS.md](VPS.md).
- Docker/Compose y storage persistente disponibles.
- Entorno protegido creado en `/etc/drivempvd/production.env` o
  `/etc/drivempvd/validation.env`.
- Tag de imagen inmutable; nunca `local` o `latest` para producción.
- Preflight aprobado.
- Backup/restauración verificables para una actualización.
- Credenciales de smoke en archivo `0600`, nunca como argumento.

No exponer un candidato privado hasta tener autorización, DNS y TLS.

## 3. Validación privada

El instalador documentado reproduce una instalación aislada sobre Ubuntu:

```bash
cd /srv/drivempvd
sudo bash docker/install-vps.sh \
  --mode validation \
  --release <tag-o-identificador>
```

En validación, los puertos quedan ligados a loopback. El navegador debe entrar
mediante un túnel SSH autorizado; no se publica el servicio por Internet.

## 4. Producción

1. Preparar release inmutable y registrar commit/archivo SHA-256.
2. Sincronizar un artefacto o checkout verificado.
3. Crear environment `0600` fuera del checkout.
4. Preparar `/data/storage`, certificados y webroot.
5. Ejecutar preflight.
6. Ejecutar gate de despliegue.
7. Verificar health, logs, smoke, DNS/TLS y UX.
8. Registrar informe de release, riesgos y rollback.

Preflight:

```bash
sudo python3 docker/preflight.py \
  --env-file /etc/drivempvd/production.env
```

Gate:

```bash
sudo scripts/runtime/deploy-compose.sh \
  --env-file /etc/drivempvd/production.env
```

El gate valida Compose, ejecuta preflight, realiza backup/restore cuando
corresponde, construye con `--pull`, levanta con `--wait`, escanea imágenes y
ejecuta smoke si se proporcionan credenciales.

`--skip-backup` y `--skip-smoke` no son defaults. Solo pueden usarse con
justificación explícita en el informe de release.

## 5. Verificación posterior

```bash
sudo env DRIVEMPVD_COMPOSE_ENV_FILE=/etc/drivempvd/production.env \
  bash scripts/runtime/verify-release.sh
```

Este verificará Compose, healthchecks de PostgreSQL/API/worker/frontend/Nginx
y patrones críticos recientes en logs. Añada smoke si procede.

Después validar:

- tag, commit, digest e imágenes instaladas;
- migración y estado de contenedores;
- readiness, login, CSRF, upload, preview, download, `HEAD` y Range;
- logs sin `Traceback`, `CRITICAL`, `FATAL`, `Unhandled exception` o `panic`;
- cabeceras, cookies, DNS, certificado, HSTS y firewall;
- backup/restore y plan de rollback.

## 6. No hacer

- No editar `docker/.env` de ejemplo para producción.
- No copiar secretos al checkout.
- No usar tags mutables.
- No desplegar una rama no etiquetada.
- No aplicar downgrade Alembic como rollback.
- No ejecutar `down --volumes` ni borrar storage sin restore verificado.

## 7. Producción pública pendiente

No declarar el sistema público hasta cumplir el checklist completo de
[RELEASE.md](RELEASE.md). En particular, quedan pendientes históricamente
dominio/DNS, TLS público, remoto/tag Git, 50 GiB, concurrencia, Internet y
validación visual/E2E.
