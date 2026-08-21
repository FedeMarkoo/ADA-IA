# Referencia de la API REST & SSE

El servidor web de ADA (`ada/interfaces/web/server.py`) expone una API REST y streaming sobre el puerto `5005` por defecto.

---

## 📌 Endpoints Principales

### Sistema y Salud
- `GET /api/status`: Retorna el estado del agente, motores activos, hardware y versión.
- `GET /api/healthcheck`: Ejecuta el diagnóstico de 7 subsistemas mediante `HealthDoctor`.
- `POST /api/doctor/heal-all`: Ejecuta todas las acciones de auto-remediación pendientes.
- `POST /api/doctor/fix`: Ejecuta una acción de reparación puntual (`action_id`).

### Chat & Streaming
- `POST /api/chat`: Procesa un mensaje de forma síncrona y devuelve la respuesta.
- `POST /api/chat/stream`: Procesa un mensaje mediante Server-Sent Events (SSE), transmitiendo actualizaciones de estado y la respuesta final en tiempo real.

### MCPs (Model Context Protocol)
- `GET /api/mcps/servers`: Lista todos los servidores MCP registrados en `mcps/config.json`.
- `POST /api/mcps/servers/<name>/restart`: Reinicia un servidor MCP específico.
- `POST /api/mcps/servers/restart-all`: Reinicia todos los servidores MCP locales.
- `GET /api/mcps/tools`: Lista todas las herramientas descubiertas dinámicamente.
- `POST /api/mcps/tools/run`: Ejecuta una herramienta MCP por nombre con parámetros JSON.
- `POST /api/mcps/tools/toggle`: Habilita o deshabilita una herramienta específica.

### Modelos y Ollama
- `GET /api/ollama/models`: Lista los modelos instalados localmente en Ollama.
- `GET /api/ollama/status`: Estado del daemon de Ollama.
- `POST /api/ollama/start`: Inicia el servicio local de Ollama.
- `POST /api/ollama/stop`: Detiene el servicio de Ollama.
- `POST /api/ollama/unload`: Descarga un modelo de la memoria VRAM.
- `GET /api/models/catalog`: Catálogo de modelos disponibles y recomendados.
- `GET /api/models/policy`: Mapeo actual de roles (`general`, `coding`, `vision`, `router`).
- `POST /api/models/benchmark`: Ejecuta un benchmark de tokens por segundo sobre un modelo.

### Telegram Bot
- `GET /api/telegram/status`: Estado del servicio (online, offline, token enmascarado, inbox).
- `POST /api/telegram/start`: Inicia el daemon de Telegram Bot en segundo plano.
- `POST /api/telegram/stop`: Detiene el daemon de Telegram Bot.
- `POST /api/telegram/restart`: Reinicia el servicio.
- `POST /api/telegram/test`: Valida el token con `getMe` ante la API de Telegram.
