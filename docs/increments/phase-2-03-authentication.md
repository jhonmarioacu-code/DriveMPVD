# Fase 2.3: autenticación del administrador

- Estado: implementado y validado
- Fecha: 2026-07-18

## Entregado

- Singleton administrador con bootstrap CLI y constraint PostgreSQL.
- Argon2id, rehash por política y verificación dummy anti-enumeración.
- Access/refresh JWT, rotación, replay detection y revocación inmediata.
- Cookies seguras como opción principal y transporte Bearer explícito.
- CSRF ligado a sesión para cookie access/refresh.
- Rate limiting PostgreSQL atómico y lockout por credenciales.
- Eventos de seguridad pseudonimizados.
- Middleware ASGI inyectado y sin dependencias de dominio/infraestructura.
- OpenAPI con esquemas Bearer/cookie.

## Estructura añadida

```text
backend/app/
├── domain/auth/{entities,enums}.py
├── application/
│   ├── dtos/auth.py
│   ├── ports/{auth_repositories,auth_services}.py
│   └── use_cases/auth/
├── infrastructure/
│   ├── security/{passwords,jwt_provider,secrets,clock}.py
│   ├── persistence/models/auth.py
│   ├── persistence/repositories/auth.py
│   └── cli/create_admin.py
└── presentation/
    ├── middleware/authentication.py
    ├── api/v1/auth.py
    └── schemas/auth.py
```

## Migración

`20260718_0002_create_authentication` crea `admin_accounts`, `auth_sessions`,
`security_events` y `auth_rate_limits`, triggers auditables, constraints UUID v7
e índices. Downgrade elimina exactamente esos objetos; la suite ejecuta
base/head/check y no detecta drift.

Índices principales:

- sesión por PK para autenticar y rotar;
- sesiones activas `(admin_id, expires_at)` parcial para revocación/limpieza;
- `family_id` y `refresh_jti` único para investigación y consistencia;
- eventos por `(event_type, occurred_at, id)`, administrador y sesión;
- rate buckets únicos por `(scope, subject_hash)` y limpieza por `updated_at`.

## Validación

| Control                | Resultado                           |
| ---------------------- | ----------------------------------- |
| Black                  | 100 archivos sin cambios requeridos |
| Ruff                   | Sin incidencias                     |
| MyPy estricto          | 100 archivos sin incidencias        |
| Pytest                 | 51 pruebas superadas                |
| Cobertura líneas/ramas | 92,31 %; mínimo 90 %                |
| PostgreSQL             | 16.14 real                          |
| Alembic                | downgrade/upgrade/check sin drift   |

## Riesgos y recomendaciones

- Repetir CI en Ubuntu/Python 3.13/Compose antes del despliegue.
- Configurar proxy IP confiable y límites Nginx adicionales.
- Añadir MFA antes de exponer el servicio a Internet si el riesgo lo requiere.
- Diseñar retención/alertas para eventos y limpieza de buckets/sesiones expiradas.
- Preparar procedimiento local probado de recuperación y rotación de secretos.
- Mantener el siguiente incremento en diseño de dominio de almacenamiento; no
  mezclar todavía sus aggregates con rutas del explorador.
