# ADR-0006: Contratos transversales del backend

- Estado: aceptada
- Fecha: 2026-07-18

## Contexto

Configuración, errores, logging y respuestas deben ser uniformes desde el
primer endpoint para evitar convenciones incompatibles entre módulos.

## Decisión

Usar un único `Settings` de `pydantic-settings`, logging JSON sobre la librería
estándar, jerarquías de excepción por capa y un envelope genérico
`data/error/meta`. OpenAPI generado por FastAPI es la fuente única de schemas y
documentación interactiva. Los binarios/streams y respuestas HTTP sin body son
las únicas excepciones justificadas al envelope JSON.

El almacenamiento se consume exclusivamente mediante `FileStorageProvider`,
que acepta iteradores asíncronos y claves opacas; ningún método materializa un
archivo completo.

## Consecuencias

Todos los módulos futuros heredan contratos ya probados. Los adaptadores pueden
cambiar sin afectar dominio. Los handlers deben sanitizar fallos inesperados y
la CI debe impedir que se rompan el formato OpenAPI, la dirección de imports o
el umbral de cobertura.
