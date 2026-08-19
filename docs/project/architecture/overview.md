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

- `src/ada/application/agent.py`: compatibilidad/orquestación existente.
- `src/ada/application/services/chat.py`: caso de uso de chat con sesiones aisladas.
- `src/ada/application/planner.py` y `src/ada/domain/`: planes, acciones y políticas
  independientes de Flask/Ollama.
- `src/ada/application/router.py`: clasifica intenciones, valida planes y usa
  un fallback determinístico cuando el motor no está disponible.
- `src/ada/infrastructure/engines/`: abstrae Ollama y motores opcionales.
- `src/ada/infrastructure/runtime/`: administra procesos, salud y recursos.
- `src/ada/infrastructure/persistence/sqlite.py`: memoria persistente SQLite.
- `src/ada/agents/`: registro, coordinador y especialistas.
- `src/ada/capabilities/`: capacidades ejecutables agrupadas por categoría.
- `src/ada/interfaces/web/server.py`, `src/ada/interfaces/web/asgi.py`, `src/ada/interfaces/telegram.py` y `ui/`:
  adapters de entrada/salida que llegan al mismo flujo de conversación.
- `src/ada/infrastructure/runtime/resources.py`: presupuesto de CPU, concurrencia y throttling.
- `src/ada/infrastructure/runtime/event_bus.py`, `scheduler.py`, `watchers.py`:
  autonomía durable y eventos.

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

El scheduler, los watchers, el supervisor multiproceso, voz local y notifiers
ya tienen contratos/implementaciones locales; las reglas de producto y los
adaptadores móviles se agregan sobre el mismo event bus. Las acciones autónomas
son pausables, trazables y revocables.

## Routing inteligente

Las órdenes explícitas se resuelven primero con reglas seguras para evitar una
llamada innecesaria al modelo. Las solicitudes abiertas pasan por
`IntentRouter`, que solicita una intención y un plan JSON al motor configurado,
valida las capabilities resultantes y conserva un fallback semántico local.
El router nunca ejecuta directamente una respuesta del modelo: solo produce un
plan validado que el agente y las interfaces pueden ejecutar con sus controles.

El proveedor no forma parte del contrato de una conversación. Se selecciona en
`config.json` mediante `engine_provider`; cambiarlo no modifica las interfaces,
el router ni las capabilities.
