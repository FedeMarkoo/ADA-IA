# ADR-001: Hexagonal y organización por contexto

- Estado: aceptada
- Fecha: 2026-08-28

## Contexto

ADA debe cambiar interfaces, proveedores LLM y persistencia sin arrastrar esos
cambios al dominio.

## Decisión

Usar arquitectura hexagonal con paquetes agrupados por contexto funcional.
Los puertos viven junto a los casos de uso y los adaptadores implementan esos
puertos.

## Consecuencias

El dominio es portable y testeable. Hay más tipos y mapeos, pero el costo es
intencional: evita acoplamiento accidental y hace visibles los contratos.
