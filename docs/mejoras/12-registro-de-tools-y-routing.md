# 12. Registro único de tools y routing estructurado

## Objetivo

Reemplazar el muro de regex para detectar intenciones por un registro único de herramientas que alimente comandos directos, routing, validación y ejecución.

## Estado de implementación

| ID | Mejora / Corrección | Estado |
|---|---|---|
| ARQ-04 | Registro único con nombre, descripción, JSON Schema, handler y confirmación | 🟡 Propuesto |
| ARQ-05 | Dispatcher exacto para comandos `/v`, `/i`, `/r`, etc. | 🟡 Propuesto |
| ARQ-06 | Router pequeño, determinista y sin contexto completo | 🟡 Propuesto |
| ARQ-07 | Validación de tool y parámetros antes de ejecutar; fallback a chat | 🟡 Propuesto |

## Flujo

```text
mensaje
  ├─ comando exacto ───────────────► dispatcher
  └─ mensaje normal ─► router JSON ─► validar + confirmar ─► ejecutar
                                      └─ sin tool / dudoso ─► chat con contexto
```

## Diseño

Cada tool debe declarar como mínimo:

- nombre y descripción para el router;
- parámetros como JSON Schema;
- handler real;
- comando opcional;
- `requires_confirmation`.

El router debe trabajar con contexto mínimo, temperatura cero y salida estructurada. El código debe verificar que la tool exista, que la confianza supere el umbral, que los parámetros cumplan el schema y que la confirmación sea válida. El modelo nunca debe ejecutar directamente.

## Beneficios y límites

- Agregar una capacidad requiere registrarla una sola vez.
- Se elimina la duplicación de listas y patrones por idioma.
- Los comandos obvios siguen siendo instantáneos y sin modelo.
- Las referencias como “ahí adentro” pueden requerir las últimas líneas de contexto, aunque no el historial completo.
- El router añade una llamada pequeña; conviene medirlo y mantener fallback claro si falla.
