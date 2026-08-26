# Catálogo completo de funcionalidades

Relación entre capacidades visibles, servidores MCP y rutas del dashboard.

## Capacidades de dominio

| Área | Funciones |
|---|---|
| Chat y razonamiento | Conversación, complejidad, memoria contextual, router, planner y respuestas |
| Archivos | Listar, agrupar, leer/escribir y resolver alias de carpetas |
| Fotografía | Análisis técnico, visión, ráfagas, RAW, XMP, Lightroom, organización y selección |
| Comida | Recetas, inventario, alacena, compras, planificación y presupuesto |
| Sistema | Scripts/comandos controlados y health checks |
| Web | Búsqueda con fallback y presupuesto |
| Datos externos | Gmail, Drive, Calendar, transporte de Buenos Aires, Git e Instagram |
| Automatización | Telegram, dispositivos extraíbles, calendario, cron, webhook, digest y alertas |
| Operación | Ollama, runtime local, modelos, benchmarks, MCPs, memoria, auditoría, Prometheus y actualización |

## Servidores MCP configurados

| Servidor | Transporte | Responsabilidad |
|---|---|---|
| `filesystem` | stdio | Operaciones seguras de archivos |
| `web-search` | stdio | Búsqueda web |
| `photography` | stdio | Fotografía y Lightroom |
| `food` | stdio | Recetas, inventario y compras |
| `transport` | stdio | Transporte público |
| `system-runner` | stdio | Comandos permitidos |
| `google-gmail` | SSE | Gmail oficial |
| `google-drive` | SSE | Drive oficial |
| `google-calendar` | SSE | Calendar oficial |
| `sqlite-memory` | stdio | SQLite de memoria |
| `git` | stdio | Control de versiones |

La lista efectiva de tools es dinámica: `ada/capabilities/registry.py` descubre módulos con `run`, recoge `CAPABILITY_SPEC` y publica schema, versión, permisos, riesgo y requisito de confirmación.

## Rutas de la API

### Estado y observabilidad

`GET /api/status`, `/api/core/state`, `/api/health`, `/api/healthcheck`, `/metrics`, `/api/audit` y `/api/memory/stats`.

### Chat y conversación

`POST /api/chat`, `POST /api/chat/stream` (SSE) y `GET/DELETE /api/conversation`.

### Ollama y modelos

`/api/ollama/status`, `/models`, `/running`, `/details`, `/config`, `/start`, `/stop`, `/restart`, `/load`, `/unload`, `/preload_all`, `/delete` y `/pull/stream`.

Política y catálogo: `/api/models/catalog`, `/api/models/policy`, `/api/models/reload`, `/api/models/benchmark` y `/api/models/benchmark/prompts`.

### Healthcheck funcional

`/api/healthcheck/prompts`, `/run`, `/runs/active`, `/batches`, `/latest`, `/history`, `/runs/<run_id>`, `/runs/<run_id>/cancel`, `/heal` y `/fix/<action_id>`.

### MCP

`/api/mcps/config`, `/servers`, `/servers/<name>/start`, `/stop`, `/restart`, `/ping`, `/servers/start-all`, `/stop-all`, `/restart-all`, `/tools`, `/tools/toggle` y `/tools/run`.

### Telegram, triggers y credenciales

`/api/telegram/status`, `/start`, `/stop`, `/restart`, `/test`, `/history`, `/config`; `/api/triggers` y `/api/triggers/<trigger_id>/<action>`; `/api/vault/keys`, `/api/vault/set` y `/api/vault/<name>`.

### Configuración y mantenimiento

`/api/config`, `/api/debug`, `/api/warmup`, `/api/restart-all`, `/api/agent/start`, `/api/agent/stop` y `/api/agent/restart`.

