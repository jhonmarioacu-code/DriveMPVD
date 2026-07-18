# Despliegue y operación previstos

Este documento fija el diseño operativo. Los comandos exactos se añadirán y se
probarán cuando Dockerfiles, Compose y migraciones existan; no se ofrecen ahora
instrucciones que aparenten ser ejecutables.

## Topología Compose

```text
Internet -> Nginx -> frontend estático
                  -> FastAPI /api
                  -> contenido interno autorizado
                       |
                 PostgreSQL
                       |
                 media worker

Host: /data/storage -> api/nginx/worker con permisos mínimos diferenciados
Volúmenes: postgres_data, certificados y configuración/secrets
```

Servicios previstos: `nginx`, `api`, `worker`, `postgres`. API y worker usan la
misma imagen versionada. PostgreSQL queda en red interna y tendrá healthcheck.
Nginx es el único servicio con puertos publicados.

Las imágenes finales usarán Python 3.13 y PostgreSQL 16. La compilación y las
pruebas de Compose se ejecutarán para Ubuntu Server 24.04 LTS. Toda configuración
de runtime entra mediante variables `DRIVEMPVD_*` validadas por `Settings`.

## Instalación

La guía final verificará Ubuntu 24.04, espacio, filesystem, reloj, Docker Engine
y Compose plugin; creará el usuario de servicio y `/data/storage` con permisos
restrictivos; instalará secretos; construirá imágenes con versiones fijadas;
ejecutará migraciones; creará la cuenta administradora mediante entrada segura;
y validará healthchecks, TLS y subida/descarga de humo.

## Actualización

Las versiones serán tags inmutables. El procedimiento final incluirá backup,
pull/build, migración compatible, recreación controlada, smoke tests y rollback
de imagen. Una migración destructiva requerirá fase de compatibilidad previa;
no se hará downgrade de base de datos a ciegas.

## Backup

Se respaldarán dump/snapshot consistente de PostgreSQL, `objects`, secretos
necesarios y manifiesto de versiones. Se excluirán staging, derivados y logs.
La retención y destino deben estar fuera del SSD principal, con cifrado,
checksums y prueba periódica de restauración.

## Restauración

La restauración se ensayará en un directorio y base aislados: desplegar versión
compatible, restaurar PostgreSQL y objetos, ejecutar verificador de referencias,
regenerar derivados, hacer smoke tests y solo entonces cambiar tráfico. El RPO
y RTO reales se documentarán tras medir el volumen del usuario.

## Mantenimiento

- Alertar por poco disco antes de impedir staging o PostgreSQL.
- Limpiar sesiones expiradas, staging y blobs huérfanos mediante jobs seguros.
- Observar autovacuum, crecimiento de índices, backlog y errores de codecs.
- Rotar logs fuera de los volúmenes de datos.
- Renovar TLS y rotar secretos con revocación de sesiones cuando aplique.

## Configuración

Toda configuración tendrá validación al inicio y valores seguros. Rutas,
orígenes, límites, claves, DSN y parámetros de Argon2 serán explícitos. La app
fallará al arrancar si usa una clave por defecto, una raíz no confinada o un
origen inseguro en producción.
