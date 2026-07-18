# ADR-0003: Cola durable en PostgreSQL

- Estado: aceptada
- Fecha: 2026-07-18

## Contexto

Miniaturas, copias grandes y limpieza deben sobrevivir reinicios. Añadir Redis o
un broker aumenta operación para un único servidor.

## Decisión

Persistir jobs en PostgreSQL y reclamarlos mediante leases y
`FOR UPDATE SKIP LOCKED`. Ejecutarlos en un worker separado usando handlers
idempotentes y payloads versionados.

## Consecuencias

Se reutiliza una dependencia ya necesaria y hay entrega al menos una vez. Los
handlers deben tolerar duplicados y la base no debe usarse para transportar
bytes de archivos. Si el volumen futuro lo exige, el puerto permite cambiar el
adaptador.
