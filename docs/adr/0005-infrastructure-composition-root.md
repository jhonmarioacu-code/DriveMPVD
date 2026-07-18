# ADR-0005: Composition root en infraestructura

- Estado: aceptada
- Fecha: 2026-07-18

## Contexto

La inyección debe ocurrir únicamente en infraestructura y las capas interiores
no pueden resolver dependencias ni conocer implementaciones.

## Decisión

Ubicar el único composition root en `infrastructure`. Allí se carga `Settings`,
se construyen adaptadores y se inyectan por constructor en casos de uso. Las
factories de `presentation` reciben casos de uso completamente construidos; no
usan un service locator para resolver infraestructura.

## Consecuencias

El arranque depende de todas las capas exteriores, como corresponde al punto de
composición. Dominio y aplicación permanecen independientes. Las pruebas pueden
inyectar fakes directamente sin levantar FastAPI ni el contenedor.
