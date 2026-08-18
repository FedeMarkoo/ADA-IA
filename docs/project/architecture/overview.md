# Arquitectura

La propuesta detallada para dejar de tener módulos sueltos en la raíz está en
[Estructura de carpetas](folder-structure.md).

## Flujo principal

```text
mensaje o evento
      ↓
parser y router
      ↓
capability, agente especialista o motor
      ↓
confirmación si hay riesgo
      ↓
ejecución y reporte
      ↓
memoria y auditoría
```

## Componentes

- `src/ada/application/agent.py`: interpreta solicitudes y selecciona acciones.
- `src/ada/infrastructure/engines/`: abstrae Ollama y motores opcionales.
- `src/ada/infrastructure/runtime/`: administra procesos, salud y recursos.
- `src/ada/infrastructure/persistence/sqlite.py`: memoria persistente SQLite.
- `src/ada/agents/`: registro, coordinador y especialistas.
- `src/ada/capabilities/`: capacidades ejecutables agrupadas por categoría.
- `src/ada/interfaces/web/server.py` y `ui/`: conversación web e historial.
- `src/ada/infrastructure/runtime/resources.py`: presupuesto de CPU, concurrencia y throttling.

## Workflow de fotos

`MultiAgentCoordinator` combina:

- `technical_photo`: enfoque, exposición, ruido, ISO y métricas locales;
- `context_photo`: sujeto, evento, estilo y coincidencia con la sesión;
- `photo_reviewer`: selección, rating, problemas y recomendación.

El mismo workflow se usa para una foto individual y para cada archivo de un
lote. Esto evita que el modo lote tenga reglas distintas o decisiones ocultas.

## Autonomía futura

La evolución prevista es:

```text
watcher → evento → regla → tarea → agente → acción → auditoría
```

El scheduler, los watchers y los adaptadores móviles todavía son trabajo
pendiente. Las acciones autónomas deberán ser pausables, trazables y revocables.
