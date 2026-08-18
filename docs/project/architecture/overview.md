# Arquitectura

La propuesta detallada para dejar de tener módulos sueltos en la raíz está en
[Estructura de carpetas](folder-structure.md).

## Flujo principal

```text
mensaje o evento
      ↓
parser y router
      ↓
skill, agente especialista o motor
      ↓
confirmación si hay riesgo
      ↓
ejecución y reporte
      ↓
memoria y auditoría
```

## Componentes

- `agent_loop.py`: interpreta solicitudes y selecciona acciones.
- `models.py`: abstrae Ollama y motores opcionales.
- `runtime.py`: administra el runtime local de Ollama.
- `memory.py`: memoria persistente SQLite.
- `agents/`: registro, coordinador y especialistas.
- `skills/`: capacidades ejecutables agrupadas por categoría.
- `ui_server.py` y `ui/`: conversación web e historial.
- `resource_policy.py`: presupuesto de CPU, concurrencia y throttling.

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
