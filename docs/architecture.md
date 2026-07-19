# Arquitectura

## Principios

DriveMPVD es un **monolito modular** para un administrador único. Un solo
artefacto backend reduce el coste operativo, mientras los límites internos
permiten extraer procesos o añadir módulos sin romper el dominio existente.

Se aplican estas reglas:

1. Las dependencias siempre apuntan hacia el dominio.
2. Cada caso de uso representa una intención y una transacción.
3. Los detalles externos se acceden por puertos e implementan con adaptadores.
4. REST, ORM, archivos y codecs no atraviesan los límites de capa.
5. Los módulos se comunican mediante contratos de aplicación o eventos, no
   usando tablas ajenas.
6. No existe registro, multitenencia, roles, ACL ni `user_id` propagado por el
   catálogo. Hay exactamente una cuenta administradora.
7. Toda comunicación entre capas cruza interfaces, casos de uso y DTOs; nunca
   modelos ORM, objetos de FastAPI ni diccionarios sin tipo.
8. Todo símbolo público tiene type hints y MyPy se ejecuta en modo estricto.

## Capas y regla de dependencias

```text
infrastructure (composition root)
       |                 |
       v                 v
presentation ------> application ------> domain
       |                 |                  |
       └──────────────> shared <────────────┘
```

- `domain`: comportamiento y lenguaje del negocio, sin frameworks.
- `application`: casos de uso, DTOs y puertos; coordina dominio y transacción.
- `infrastructure`: adaptadores de PostgreSQL, almacenamiento, criptografía y
  medios; contiene el único composition root.
- `presentation`: HTTP. Recibe casos de uso construidos y traduce DTOs.
- `shared`: tipos transversales mínimos y estables.

La inyección es explícita por constructor y ocurre únicamente en
`infrastructure`. El composition root crea adaptadores y casos de uso, y los
entrega a factories de rutas. `presentation` no usa un service locator ni
resuelve adaptadores con `Depends`; los casos de uso reciben interfaces, no
contenedores globales.

## Configuración

Un único `Settings` tipado, implementado con `pydantic-settings`, obtiene toda
configuración desde variables de entorno con prefijo `DRIVEMPVD_`. Ningún
módulo lee `os.environ` directamente. El composition root carga y valida una
instancia al arrancar; configuración inválida impide el inicio. No existen
secretos o valores de producción incrustados en código.

## Módulos

| Módulo      | Responsabilidad                                                                 | No conoce                       |
| ----------- | ------------------------------------------------------------------------------- | ------------------------------- |
| `catalog`   | Árbol lógico, metadatos, crear, renombrar, mover, copiar y papelera             | Rutas físicas y HTTP            |
| `transfers` | Sesiones de subida, offsets, finalización y descargas vía `FileStorageProvider` | FastAPI y nombres físicos       |
| `media`     | Detección, miniaturas, previews y derivados                                     | Credenciales y navegación UI    |
| `identity`  | Cuenta única, login, sesiones, JWT y CSRF                                       | Catálogo de archivos            |
| `activity`  | Favoritos, aperturas recientes y auditoría relevante                            | Implementación del reproductor  |
| `jobs`      | Contrato transversal de trabajos durables                                       | Reglas particulares de cada job |

Las futuras capacidades (`tags`, `sharing`, `versions`, `antivirus`, `search`
de contenido y `sync`) serán módulos nuevos. No se anticiparán con columnas
genéricas ni abstracciones sin uso.

## Flujo de una petición

```text
Nginx -> route/DTO -> caso de uso -> aggregate/servicio de dominio
                                    -> puerto -> adaptador SQL/disco
       <- respuesta HTTP <- DTO de salida <- commit Unit of Work
```

Los comandos bloquean únicamente filas necesarias. Las queries utilizan
proyecciones de lectura y no reconstruyen aggregates cuando no hace falta.

## Procesos de ejecución

- `nginx`: único borde público; termina TLS, aplica límites y cabeceras, sirve
  el fallback de la SPA mediante el contenedor de frontend y reenvía `/api`.
- `frontend`: artefactos estáticos creados por Vite, accesibles únicamente desde
  la red `edge` de Nginx.
- `api`: FastAPI asíncrono, operaciones rápidas y creación de jobs, aislado en
  la red privada junto con las migraciones.
- `migrate`: ejecución única de `alembic upgrade head` antes de iniciar la API.
- `postgres`: metadatos, sesiones, cola durable y coordinación; no publica un
  puerto en el host.

La composición normal conserva la entrega de blobs en FastAPI. La ubicación
Nginx `internal` y el overlay de sólo lectura para `X-Accel-Redirect` están
preparados, pero permanecen sin activar hasta que exista un adaptador de
entrega que preserve autorización, `HEAD`, ETag y rangos RFC 9110.

No se requiere un broker adicional en el servidor inicial ni se declara un
worker vacío. Cuando exista un ejecutor de jobs real, podrá usar la misma imagen
de backend y escalar de forma independiente.

## Consistencia y transacciones

- PostgreSQL es la fuente de verdad de metadatos; el blob es contenido opaco.
- Una Unit of Work abarca cada comando.
- La finalización de subida usa un archivo staging en el mismo filesystem,
  `fsync`, renombrado atómico y después commit de metadatos. Un reconciliador
  limpia huérfanos ante fallos entre pasos.
- Operaciones costosas se modelan como jobs idempotentes con reintentos y
  estado visible.
- Los eventos de dominio se persisten junto con la transacción cuando deban
  originar trabajo posterior.

## Observabilidad

Logs JSON a stdout incluirán `request_id`, caso de uso, duración y resultado,
nunca tokens, contraseñas ni nombres sensibles completos. Se expondrán probes
separadas de vida y disponibilidad. Las métricas mínimas cubrirán latencia,
errores, bytes subidos/servidos, backlog y fallos de trabajos.

El logging usa un formatter JSON sobre la librería estándar y campos tipados;
no concatena líneas libres. Un middleware propaga `request_id`. Excepciones
base separadas para dominio, aplicación e infraestructura son capturadas por un
manejador global en el borde HTTP; el detalle interno solo va al log.

## Versionado

La API comienza en `/api/v1`. Swagger UI, ReDoc y cualquier referencia de
endpoints se generan automáticamente desde el documento OpenAPI producido por
FastAPI. No se mantienen descripciones manuales paralelas. Cambios aditivos
conservan la versión; cambios
incompatibles requieren `/api/v2`. Las migraciones de Alembic son progresivas
y compatibles con el orden `expand -> migrate -> contract` cuando una
actualización no pueda ser atómica.

## Línea base tecnológica

- Python 3.13 como runtime de contenedor.
- FastAPI estable y SQLAlchemy 2.x.
- PostgreSQL 16.
- React 19 y TypeScript 5.x cuando comience la Fase 3.
- Docker Compose sobre Ubuntu Server 24.04 LTS.

Se usan dependencias estables, mantenidas y con versiones acotadas. No se
adoptan APIs experimentales, prereleases ni paquetes sin mantenimiento activo.
