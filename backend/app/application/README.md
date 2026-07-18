# Application

Orquesta casos de uso mediante commands y queries. Define DTOs inmutables,
puertos de repositorio, unidad de trabajo, reloj, hashing, tokens,
almacenamiento de blobs y cola de trabajos.

`FileStorageProvider` es el único acceso al contenido físico. Sus métodos son
streaming y pueden ser implementados por almacenamiento local, S3 o MinIO sin
cambiar dominio ni casos de uso.

Puede depender de `domain` y `shared`, pero no de `infrastructure` ni de
`presentation`. Las transacciones se delimitan por caso de uso.
