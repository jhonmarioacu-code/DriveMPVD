# Releases, sincronización y puerta de producción

## 1. Principio

Una build correcta no es un release. Un release requiere trazabilidad, pruebas,
seguridad, recuperación, operación y evidencia. Una candidata privada no es
producción pública.

## 2. Trazabilidad Git

El estado histórico documentado indicaba:

- `.git` local presente, pero Git no disponible en `PATH`;
- ningún remoto configurado;
- VPS con copia de despliegue, no worktree Git.

Antes de producción pública, verificar y completar:

1. Git local operativo.
2. Remoto autorizado.
3. Tag inmutable publicado.
4. SHA completo resuelto.
5. Checkout limpio.
6. Manifiesto de release.
7. Despliegue desde checkout/artefacto versionado.

No asumir que esas condiciones se resolvieron por una evidencia anterior.

## 3. Preparar release

`scripts/release/prepare-release.sh` exige un checkout limpio y tag o SHA:

```bash
scripts/release/prepare-release.sh \
  --ref <tag-inmutable-o-sha-completo> \
  --output <ruta-segura-del-manifiesto>
```

El manifiesto registra referencia, commit, SHA-256 del archive y hora. No
incluye credenciales.

Reglas:

- no desplegar ramas flotantes;
- no usar `latest` o `local` como tag de producción;
- no sobrescribir un tag de release;
- no preparar release con working tree sucio;
- registrar imágenes, digests, commit, tag y environment utilizado.

## 4. Sincronización Local–Git–VPS

```mermaid
flowchart LR
  L[Checkout local limpio] --> G[Tag Git inmutable]
  G --> M[Manifiesto de release]
  M --> A[Artefacto verificado]
  A --> V[/srv/drivempvd/releases/commit]
  V --> C[Candidata y gates]
  C --> P[Producción autorizada]
```

Antes de limpiar, promover o declarar igualdad:

1. Definir conjunto canónico de código, docs, scripts y ejemplos.
2. Excluir `.git`, dependencies, caches, env reales, certificados, datos,
   backups y artefactos generados.
3. Generar SHA-256 por ruta en origen y destino.
4. Comparar conteos, rutas solo-local, solo-remoto y contenido distinto.
5. Generar digest canónico del manifiesto ordenado.
6. Guardar exclusiones, origen/destino, fecha, hash y resultado.

El estado correcto es `only_local=0`, `only_vps=0`,
`content_different=0` y digest igual. Una sincronización no autoriza borrar la
única copia, datos o backups.

## 5. Transferencia

`scripts/transfer/push-rsync.sh`:

```bash
scripts/transfer/push-rsync.sh \
  --target <usuario>@<host> \
  --apply
```

Sin `--apply` solo valida prerrequisitos. Con `--apply` crea un directorio
hash-verificado bajo `/srv/drivempvd/releases/<commit>`; no cambia
`/srv/drivempvd` ni inicia servicios.

SCP/SFTP siguen el mismo principio. FTP se rechaza explícitamente.

En Windows, `scripts/Deploy-DriveMPVD.ps1` orquesta una instalación desde un
checkout Git limpio: exige `git`, `ssh` y `scp`, valida que el release resuelva
al HEAD revisado y requiere dominio/correo en modo production. No usarlo con
una clave o servidor no autorizados.

## 6. Checklist de Release Candidate

- [ ] Requisitos/criterios de aceptación trazados.
- [ ] Checkout limpio, commit y tag/SHA identificados.
- [ ] Frontend: formato, lint, tipos, tests y build aprobados.
- [ ] Backend: Black, Ruff, MyPy, Pytest y cobertura aprobados.
- [ ] PostgreSQL 16 y migraciones validadas.
- [ ] Compose config/preflight aprobados.
- [ ] Scans de fuente, dependencias e imágenes aprobados.
- [ ] Candidata aislada levanta con servicios healthy.
- [ ] Smoke autenticado pasa y limpia fixtures.
- [ ] Backup + restore drill aislado pasan.
- [ ] Logs revisados sin patrones críticos.
- [ ] UX manual del alcance afectado registrada.
- [ ] Riesgos abiertos documentados y aceptados.

## 7. Puerta de producción pública

**No marcar como listo para producción mientras falte una puerta.**

| Puerta | Evidencia requerida |
| --- | --- |
| Trazabilidad | Git/remote/tag inmutable, manifiesto, checkout limpio y sincronización certificada. |
| Código | Gates backend/frontend sin reducción de umbral. |
| Datos | Migraciones compatibles, PostgreSQL real e integridad/restore drill. |
| Storage | Upload/download/Range/outbox y recuperación verificados. |
| Seguridad | Scans, secretos fuera de Git, CSRF/cookies/headers/permisos/firewall. |
| Infra | Host, Docker/Nginx, recursos, puertos y logs validados. |
| Dominio/TLS | DNS, certificado válido, renovación dry-run, HSTS y smoke contra hostname. |
| Rendimiento | 50 GiB, concurrencia, Internet y métricas reproducibles. |
| UX | Browser real, responsive, accesibilidad y media verificadas. |
| Backups | Cifrado offsite, retención, RPO/RTO, restore aplicable probado. |
| Operación | Runbooks, mantenimiento, incidentes y rollback ensayados. |
| Riesgos | Ningún riesgo alto abierto; los demás tienen propietario y plan. |

## 8. Bloqueos conocidos

La candidata no debe exponerse públicamente hasta resolver:

- dominio/DNS y TLS público;
- autorización de apertura 80/443;
- remoto Git/tag/release inmutable;
- backup offsite/retención/RPO/RTO;
- benchmark 50 GiB, concurrencia e Internet;
- E2E/browser manual;
- pendientes de papelera frontend, staging/outbox/media.

## 9. Cierre de release

Actualizar:

- [CHANGELOG.md](CHANGELOG.md);
- documentación temática afectada;
- evidencia de tests, scans, deploy y restore;
- riesgos/pendientes;
- informe de versión: tag, commit, imágenes, digests, fecha, operador,
  comandos y resultado.

La promoción requiere autorización explícita del propietario.
