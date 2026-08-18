# Estructura propuesta del proyecto

## Problema actual

La raíz mezcla entrypoints, núcleo, runtime, memoria, adaptadores y utilidades:

```text
ada.py  agent.py  agent_loop.py  memory.py  models.py  runtime.py
image_embedding.py  mcp_client.py  resource_policy.py  ui_server.py
```

Esto dificulta descubrir responsabilidades, probar módulos y agregar nuevos
canales o agentes. `agents/` y `skills/` ya tienen una separación útil, pero el
núcleo todavía está disperso.

## Estructura objetivo

```text
ada/
├── pyproject.toml
├── README.md
├── config/
│   ├── default.json
│   └── local.example.json
├── src/
│   └── ada/
│       ├── __init__.py
│       ├── cli.py
│       ├── application.py
│       ├── core/
│       │   ├── agent.py
│       │   ├── router.py
│       │   ├── tasks.py
│       │   ├── events.py
│       │   └── audit.py
│       ├── memory/
│       │   ├── store.py
│       │   ├── models.py
│       │   └── retrieval.py
│       ├── runtime/
│       │   ├── model_manager.py
│       │   ├── ollama.py
│       │   ├── resources.py
│       │   └── health.py
│       ├── agents/
│       │   ├── registry.py
│       │   ├── coordinator.py
│       │   └── photo/
│       ├── skills/
│       │   ├── registry.py
│       │   ├── files/
│       │   ├── photos/
│       │   ├── data/
│       │   └── system/
│       ├── media/
│       │   ├── raw.py
│       │   ├── vision.py
│       │   ├── metadata.py
│       │   ├── bursts.py
│       │   └── xmp.py
│       ├── adapters/
│       │   ├── web/
│       │   ├── telegram/
│       │   └── mobile/
│       └── infrastructure/
│           ├── filesystem.py
│           ├── sqlite.py
│           └── mcp.py
├── tests/
├── scripts/
└── docs/
```

## Qué queda en cada zona

- `core/`: decisiones del agente, routing, eventos, tareas y auditoría; no
  debería importar Flask ni detalles de Ollama.
- `memory/`: persistencia y recuperación; ninguna skill debería abrir SQLite
  directamente.
- `runtime/`: proveedores de modelos, lifecycle y límites de recursos.
- `agents/`: especialistas y coordinación multiagente.
- `skills/`: capacidades ejecutables; cada skill conserva una interfaz clara
  `run(args)` durante la migración.
- `media/`: decodificación RAW, visión, metadatos, ráfagas y XMP compartidos
  por las skills de fotos.
- `adapters/`: entradas y salidas: web, Telegram, CLI y móvil. No contienen la
  lógica de negocio.
- `infrastructure/`: acceso a filesystem, SQLite y MCP.

## Mapeo desde la estructura actual

| Actual | Destino |
|---|---|
| `agent_loop.py` | `src/ada/core/router.py` y `core/agent.py` |
| `agent.py` | `src/ada/core/application.py` o `core/legacy.py` |
| `memory.py` | `src/ada/memory/store.py` |
| `models.py` | `src/ada/runtime/model_manager.py` |
| `runtime.py` | `src/ada/runtime/ollama.py` y `runtime/health.py` |
| `resource_policy.py` | `src/ada/runtime/resources.py` |
| `image_embedding.py` | `src/ada/media/embeddings.py` |
| `mcp_client.py` | `src/ada/infrastructure/mcp.py` |
| `ui_server.py` | `src/ada/adapters/web/server.py` |
| `skills/photos/analyze_photo.py` | `src/ada/skills/photos/analyze.py` |
| `skills/photos/burst_detection.py` | `src/ada/media/bursts.py` |
| `skills/photos/xmp.py` | `src/ada/media/xmp.py` |
| `ada.py` | `src/ada/cli.py` |

## Reglas de diseño

1. La raíz debe contener solo configuración del proyecto, packaging, README y
   carpetas estándar.
2. Los módulos ejecutables deben vivir dentro del paquete `src/ada/`.
3. Los entrypoints (`cli`, servidor web, workers) solo ensamblan dependencias;
   no contienen lógica de dominio.
4. Las skills no deben importar módulos de la interfaz.
5. Las skills de fotos deben reutilizar `media/` en lugar de duplicar decodificación
   RAW, metadatos o XMP.
6. Los adaptadores convierten mensajes externos en comandos/eventos de ADA.
7. Las rutas se obtienen de configuración, nunca de imports o strings globales.

## Migración recomendada

### Etapa 1: preparar el paquete

- agregar `pyproject.toml` y `src/ada/__init__.py`;
- crear módulos puente que reexporten las APIs actuales;
- mantener los entrypoints actuales como compatibilidad temporal;
- asegurar que las pruebas sigan pasando.

### Etapa 2: mover el núcleo

- migrar memoria, runtime, modelos y política de recursos;
- actualizar imports a `ada.memory`, `ada.runtime` y `ada.core`;
- eliminar duplicaciones y dejar archivos puente con aviso de deprecación.

### Etapa 3: separar adaptadores y media

- mover servidor web y CLI a `adapters/`;
- extraer RAW, visión, metadatos, ráfagas y XMP a `media/`;
- hacer que las skills de fotos dependan de esas interfaces.

### Etapa 4: consolidar skills

- mantener el cargador actual, pero apuntando a `ada.skills`;
- normalizar nombres y contratos de cada skill;
- eliminar archivos puente solo después de actualizar documentación y pruebas.

### Etapa 5: autonomía

- agregar `events/`, scheduler y workers bajo `core/`;
- incorporar Telegram y móvil como adaptadores independientes;
- agregar auditoría, cancelación y límites por tarea.

No se recomienda hacer un gran `mv` sin estas etapas: rompería imports,
configuración, el cargador dinámico y posibles procedimientos guardados en
memoria.
