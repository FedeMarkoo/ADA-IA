# Referencia de la API REST y SSE

El servidor web de ADA (`ada/interfaces/web/server.py`) expone una API REST y streaming sobre el puerto `5005` por defecto. Este documento también incluye el catálogo de capacidades de dominio y los servidores MCP configurados.

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

## Endpoints principales

### Sistema y salud

- `GET /api/status` — estado del agente, motores activos, hardware y versión.
- `GET /api/health`, `GET /api/healthcheck` — diagnóstico de 7 subsistemas mediante `HealthDoctor`.
- `GET /api/core/state` — estado interno del núcleo.
- `GET /metrics` — métricas Prometheus.
- `GET /api/audit` — registro de auditoría.
- `GET /api/memory/stats` — estadísticas de memoria SQLite.
- `POST /api/doctor/heal-all` — acciones de auto-remediación pendientes.
- `POST /api/doctor/fix` — reparación puntual (`action_id`).

### Chat y streaming

- `POST /api/chat` — mensaje síncrono.
- `POST /api/chat/stream` — mensaje con Server-Sent Events.
- `GET /api/conversation` — historial de conversación.
- `DELETE /api/conversation` — limpiar conversación.

### MCPs (Model Context Protocol)

- `GET /api/mcps/config` — configuración de MCPs.
- `GET /api/mcps/servers` — servidores registrados.
- `POST /api/mcps/servers/<name>/start`, `/stop`, `/restart` — control individual.
- `POST /api/mcps/servers/start-all`, `/stop-all`, `/restart-all` — control global.
- `POST /api/mcps/servers/<name>/ping` — ping a un servidor.
- `GET /api/mcps/tools` — herramientas descubiertas.
- `POST /api/mcps/tools/run` — ejecutar herramienta por nombre.
- `POST /api/mcps/tools/toggle` — habilitar/deshabilitar herramienta.

### Modelos y Ollama

- `GET /api/ollama/status` — estado del daemon.
- `GET /api/ollama/models` — modelos instalados.
- `POST /api/ollama/start`, `/stop`, `/restart` — control del daemon.
- `POST /api/ollama/load`, `/unload` — cargar/descargar modelo de VRAM.
- `POST /api/ollama/preload_all` — precargar todos los modelos asignados.
- `POST /api/ollama/delete` — eliminar un modelo.
- `POST /api/ollama/pull/stream` — descargar modelo con streaming.
- `GET /api/ollama/details`, `/config`, `/running` — detalles y configuración.
- `GET /api/models/catalog` — catálogo de modelos.
- `GET /api/models/policy` — mapeo de roles.
- `POST /api/models/reload` — recargar política.
- `POST /api/models/benchmark` — benchmark de tokens por segundo.
- `GET /api/models/benchmark/prompts` — prompts de benchmark disponibles.

### Healthcheck funcional

- `GET /api/healthcheck/prompts` — checklist funcional desde SQLite.
- `POST /api/healthcheck/prompts` — agregar caso de prueba.
- `POST /api/healthcheck/run` — ejecutar prompts con evaluación.
- `GET /api/healthcheck/runs/active` — corridas activas.
- `GET /api/healthcheck/batches` — lotes de ejecución.
- `GET /api/healthcheck/latest` — último resultado.
- `GET /api/healthcheck/history` — historial completo.
- `GET /api/healthcheck/runs/<run_id>` — resultado de una corrida.
- `POST /api/healthcheck/runs/<run_id>/cancel` — cancelar corrida.
- `POST /api/healthcheck/heal` — auto-reparar.
- `POST /api/healthcheck/fix/<action_id>` — reparación puntual.

### Telegram, triggers y credenciales

- `GET /api/telegram/status` — estado del bot.
- `POST /api/telegram/start`, `/stop`, `/restart` — control del daemon.
- `POST /api/telegram/test` — validar token.
- `GET /api/telegram/history` — conversaciones.
- `GET /api/telegram/config` — configuración.
- `GET /api/triggers` — triggers configurados.
- `POST /api/triggers/<trigger_id>/<action>` — control de triggers.
- `GET /api/vault/keys` — claves en la bóveda.
- `POST /api/vault/set` — guardar secreto.
- `DELETE /api/vault/<name>` — eliminar secreto.

### Configuración y mantenimiento

- `GET /api/config` — configuración activa.
- `GET /api/debug` — información de debug.
- `POST /api/warmup` — precalentamiento.
- `POST /api/restart-all` — reiniciar todos los servicios.
- `POST /api/agent/start`, `/stop`, `/restart` — control del agente autónomo.
