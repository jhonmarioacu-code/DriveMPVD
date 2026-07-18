# ADR-0001: Monolito modular con DDD

- Estado: aceptada
- Fecha: 2026-07-18

## Contexto

El producto sirve a un usuario en un servidor de 4 vCPU y debe ser sencillo de
mantener, pero admitir módulos futuros.

## Decisión

Usar un monolito modular con capas DDD, puertos/adaptadores e inyección por
constructor. API y worker comparten artefacto, aunque se ejecutan como procesos
separados. Las fronteras de módulo se prueban y no se accede a tablas ajenas.

## Consecuencias

Hay una sola base y ciclo de despliegue, menor coste operativo y transacciones
locales. La disciplina de dependencias es obligatoria. Un módulo solo se
extraerá si mediciones u operación lo justifican.
