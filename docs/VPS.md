# Configuración de Ubuntu Server

## 1. Perfil de host

La candidata documentada usó Ubuntu Server 24.04.4 LTS, cuatro vCPU y
aproximadamente 15 GiB de RAM. Ese dato es una línea base histórica; verificar
capacidad, disco, inodos y red del host real antes de instalar.

## 2. Paquetes base

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-buildx docker-compose-v2
sudo systemctl enable --now docker
docker version
docker compose version
```

El operador con acceso Docker posee capacidad administrativa del host. No
agregar cuentas de aplicación o compartidas al grupo Docker.

## 3. Almacenamiento persistente

Crear fuera del checkout:

```bash
sudo install -d -m 0750 -o 10001 -g 10001 /data/storage
sudo install -d -m 0750 /var/lib/drivempvd/acme-webroot
```

El UID/GID 10001 corresponde a API/worker no privilegiados. No utilizar
`/data/storage` como directorio temporal de benchmark o checkout.

## 4. Firewall y red

Para producción, abrir solo SSH, 80/TCP y 443/TCP según política aprobada.
Mantener `deny incoming` como postura inicial y reloj sincronizado. Antes de
poner un proxy/balanceador externo, configurar IP real y fuentes confiables en
Nginx.

La candidata privada debe permanecer en loopback. Una dirección IP pública no
debe considerarse autorización para exponer HTTP/HTTPS.

## 5. Entornos y secretos

| Modo | Archivo |
| --- | --- |
| Validación privada | `/etc/drivempvd/validation.env` |
| Producción | `/etc/drivempvd/production.env` |

Los archivos son `root:root`, modo `0600`, fuera de Git. Deben contener
secretos JWT independientes de al menos 32 bytes, pepper y DSN correctamente
codificado. No imprimirlos ni incluirlos en logs/backups ordinarios.

## 6. Recursos iniciales

El perfil de referencia para cuatro vCPU/16 GiB limita servicios:

| Servicio | Memoria máxima | CPU |
| --- | ---: | ---: |
| PostgreSQL | 4 GiB | 1,25 |
| API | 2 GiB | 2,0 |
| Worker | 512 MiB | 0,5 |
| Nginx | 512 MiB | 0,5 |
| Frontend | 256 MiB | 0,25 |

Es una envolvente inicial, no un SLO. Solo cambiar límites tras capturar CPU,
RSS, I/O, latencia y resultados de carga.

## 7. Validación del host

Antes de promocionar:

- Docker Engine/Compose activos.
- Rutas persistentes con propiedad/permisos correctos.
- Espacio e inodos suficientes para datos, imágenes y backup.
- Firewall y listeners comprobados.
- Entorno protegido legible solo por root.
- Certificados y webroot preparados en producción.
- Preflight, Compose config, health, logs, smoke y restore drill aprobados.

El instalador `docker/install-vps.sh` es repetible y prepara Docker, Certbot,
UFW, rutas, secretos, build, migraciones y smoke. No ejecutarlo desde un
script descargado sin revisión o hash.

## 8. Acceso privado desde navegador

Cuando el servicio está en loopback de la VPS, usar un túnel SSH autorizado
desde el PC. Ejemplo conceptual:

```powershell
ssh -N -L <puerto-local>:127.0.0.1:<puerto-vps> <usuario>@<host>
```

Abrir después `http://127.0.0.1:<puerto-local>`. No registrar IPs, usuarios ni
claves privadas en el repositorio.

## 9. Pendientes operativos

- Dominio/DNS y TLS público.
- Backup cifrado/offsite, retención, RPO/RTO y timer.
- Monitoreo/alertas con política aprobada.
- Benchmark 50 GiB, concurrencia e Internet.

## Documentación relacionada

- [Despliegue](DEPLOYMENT.md): secuencia controlada de instalación y promoción.
- [Docker](DOCKER.md) y [Nginx](NGINX.md): servicios, redes y proxy inverso.
- [Seguridad](SECURITY.md): secretos, exposición y endurecimiento.
- [Backups](BACKUP.md) y [Operaciones](OPERATIONS.md): recuperación y mantenimiento.
