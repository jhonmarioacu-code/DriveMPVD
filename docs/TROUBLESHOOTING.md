# Solución de problemas

## 1. Principio de diagnóstico

Primero recopilar evidencia de solo lectura: versión/tag, `docker compose ps`,
healthchecks, logs recientes, puertos, entorno no secreto y resultado del
último deploy. No borrar archivos, staging, volúmenes, containers ni backups
para ocultar un síntoma.

## 2. Casos frecuentes

| Síntoma | Causa probable | Acción segura |
| --- | --- | --- |
| No se abre desde Internet | Candidata ligada a loopback o firewall/DNS no configurado. | Usar túnel SSH para validación; no exponer puertos sin autorización. |
| `docker compose` exige variables | Se usó el environment incorrecto. | Usar `--env-file` protegido correcto; no imprimirlo. |
| API/worker no inicia tras deploy | `migrate` o PostgreSQL no saludables. | Revisar health/logs, migración y preflight; no reiniciar en bucle. |
| Upload se detiene/reanuda mal | Offset cliente no coincide o sesión venció. | Consultar `HEAD` y usar offset del servidor. |
| Archivo no abre inline | MIME no permitido, auth o navegador no soporta codec. | Revisar `HEAD`/headers y ofrecer descarga; no relajar allowlist. |
| Range falla | Proxy/configuración alteró headers o delivery. | Repetir smoke de `HEAD`/Range y revisar Nginx/API. |
| Error CSRF | Cookie/cabecera ausente o mismo origen roto. | Revisar cookie, `X-CSRF-Token`, HTTPS y cliente central. |
| Cobertura backend baja local | Integraciones PostgreSQL omitidas. | Ejecutar `docker/verify-postgresql-tests.sh`; no bajar 90 %. |
| Frontend recibe 401 repetidos | Refresh no serializado o sesión revocada. | Revisar cliente auth, cookies y logout; no persistir JWT. |
| Compose no puede cargar cert | PEM faltante, symlink o permiso incorrecto. | Copiar PEM dereferenciado a ruta aprobada y validar TLS. |
| Backup no se considera válido | Solo se creó dump/tar. | Ejecutar restore drill y validar hashes/revisión. |
| Objeto físico aparentemente huérfano | Carrera, outbox pendiente o referencia no revisada. | Detener borrado manual, preservar evidencia y revisar DB/outbox. |

## 3. Recuperación

- Si la migración no comenzó, rollback a imagen/tag anterior puede ser posible.
- Si la migración aplicó, no usar downgrade; restaurar backup probado en un
  entorno aislado y seguir [BACKUP.md](BACKUP.md).
- Si se detecta posible secreto expuesto, tratar como incidente de seguridad:
  preservar evidencia, restringir acceso y rotar con autorización.

## 4. Información mínima para escalar

- objetivo/entorno/fecha;
- commit/tag e imagen;
- comandos ejecutados y salida relevante sin secretos;
- healthchecks, logs y hora;
- pasos de reproducción;
- impacto en datos/usuarios;
- acciones ya realizadas;
- backup/rollback disponibles.
