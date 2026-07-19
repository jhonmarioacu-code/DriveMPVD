# Fase 9: Optimización y pruebas con archivos grandes

- Estado: implementación terminada; validación de host real pendiente
- Fecha: 2026-07-19

## Evidencia antes de optimizar

La auditoría encontró que `LocalFileStorageProvider.append_chunk` enviaba cada
fragmento ASGI a un hilo de escritura. Una prueba temporal de 128 MiB mostró
134,3 MiB/s con fragmentos de 64 KiB, frente a 275,8 MiB/s cuando el origen ya
entregaba bloques de 1 MiB. El archivo no se cargaba completo en memoria, pero
el coste de coordinación por fragmento era un cuello de botella medible.

También se comprobó que el progreso XHR actualizaba el estado React por cada
evento de red. En archivos grandes eso puede causar renders innecesarios. No se
modificaron índices de PostgreSQL: sin `EXPLAIN (ANALYZE, BUFFERS)` sobre el
dataset objetivo sería una optimización prematura.

## Implementación

- Coalescencia de escritura acotada a 1 MiB y manejo correcto de escrituras
  parciales en el adaptador local.
- Dos settings de tuning: `DRIVEMPVD_STORAGE_STREAM_BLOCK_SIZE_BYTES` y
  `DRIVEMPVD_STORAGE_WRITE_BUFFER_SIZE_BYTES`, ambos en 1 MiB por defecto y
  configurables entre 64 KiB y 16 MiB.
- Progreso de subida frontend coalescido cada 100 ms, conservando el offset más
  reciente y cancelando callbacks pendientes al finalizar o cancelar.
- `backend/scripts/benchmark_storage.py`: benchmark seguro local. Por defecto
  usa 128 MiB; una ejecución >1 GiB requiere `--allow-large` y espacio libre.
- `backend/scripts/benchmark_deployment.py`: benchmark autenticado para un
  stack desplegado; transmite por chunks, descarga sin retener el objeto, valida
  checksum y `Range`, informa throughput, p50/p95/p99 y limpia el archivo de
  prueba salvo `--keep-entry`.

## Métricas obtenidas

La comparación de 256 MiB, dos ejecuciones por configuración, en este host
Windows local fue:

| Buffer de escritura | Mediana de subida | Pico `tracemalloc` |
| ------------------- | ----------------: | -----------------: |
| 64 KiB              |      198,18 MiB/s |           ~2,0 MiB |
| 1 MiB               |      248,04 MiB/s |           ~3,1 MiB |

La mejora observada es 25,2 %. Las lecturas de 1 MiB quedaron entre 767 y 830
MiB/s. No extrapolar estas cifras a Ubuntu, contenedores o red; son evidencia
de que el cambio reduce el coste de fragmentos pequeños sin alterar el límite
de memoria.

## Validación ejecutada

- Ruff, Black y MyPy del backend, incluyendo `scripts/`: correctos.
- Pruebas focalizadas de settings y almacenamiento: 20 correctas. Suite backend
  sin cobertura: 86 correctas y 27 omitidas por falta de PostgreSQL local; la
  puerta de 90 % quedó en 62,52 % por esas integraciones omitidas.
- Frontend: TypeScript, ESLint, Prettier y build correctos; Vitest con 163
  pruebas correctas y 91,36 % de statements.
- El benchmark local, el modo de ayuda del benchmark de despliegue y los guards
  contra una ejecución grande accidental se ejecutaron correctamente.

## Pendientes de validación final

- Ejecutar `docker compose` en Ubuntu con Docker Engine y repetir el smoke test
  completo de Fase 8.
- Ejecutar `benchmark_storage.py --size-gib 50 --allow-large` sobre el volumen
  que alojará `/data/storage`.
- Ejecutar `benchmark_deployment.py` con 1 y varios clientes, registrar CPU,
  RSS, I/O, p50/p95/p99, `EXPLAIN (ANALYZE, BUFFERS)` y estadísticas de
  PostgreSQL sobre datos de escala objetivo.
- Comparar el modo actual de streaming con un adaptador real
  `X-Accel-Redirect`; no activar el overlay antes de comprobar autorización,
  `HEAD`, ETag, Range, cancelación y uso de memoria.

## Siguiente fase

La Fase 10 no se iniciará hasta la aprobación explícita del usuario.
