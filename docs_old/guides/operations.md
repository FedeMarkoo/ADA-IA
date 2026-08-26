# Operaciones, Diagnóstico y Mantenimiento

ADA-IA incluye herramientas integradas para diagnóstico continuo y auto-remediación automática.


## Métricas con Prometheus y Grafana

ADA expone métricas nativas de Prometheus en `http://127.0.0.1:5005/metrics`.
La retención y las series históricas quedan a cargo de Prometheus; Grafana es la
interfaz integrada en la pestaña **Métricas** del Dashboard de ADA.

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

Luego abrí [Grafana](http://127.0.0.1:3000) y [Prometheus](http://127.0.0.1:9090).
El dashboard `ADA / ADA — Operaciones` se provisiona automáticamente.

Si ADA corre dentro de Docker en vez de en el host, cambiá el target de
`monitoring/prometheus/prometheus.yml` por el nombre del servicio ADA.

### Familias de métricas disponibles

- `ada_mcp_tool_executions_total{mcp,tool,status}`: cantidad de ejecuciones por MCP/tool y resultado `ok` o `error`.
- `ada_mcp_tool_duration_seconds{mcp,tool,status}`: histograma de duración de cada tool.
- `ada_mcp_tool_in_flight` y `ada_mcp_in_flight`: ejecuciones actualmente activas.
- `ada_mcp_running` y `ada_mcp_tool_enabled`: estado operativo de MCPs y tools.
- `ada_mcp_memory_bytes` y `ada_mcp_cpu_seconds_total`: recursos observados por MCP/tool.
- `ada_system_memory_bytes{state}` y `ada_system_cpu_usage_ratio`: recursos disponibles del sistema.
- `ada_system_gpu_usage_ratio`, `ada_system_gpu_memory_bytes{state}` y `ada_system_gpu_available`: uso y memoria de GPU; usa `nvidia-smi` en NVIDIA y una estimación por frecuencia GT en Intel integrada.
- `ada_process_memory_bytes`, `ada_process_cpu_usage_ratio` y `ada_process_uptime_seconds`: recursos de ADA.
- `ada_component_memory_bytes{component}`, `ada_component_cpu_usage_ratio{component}` y `ada_component_running{component}`: ADA, Ollama, Telegram, Prometheus y Grafana cuando son detectables como procesos.
- `ada_responses_total{source,status}`: respuestas de ADA separadas en `ok` y `error`.

Los MCP locales se ejecutan dentro del proceso de ADA, por lo que su memoria
residente es compartida: `ada_mcp_memory_bytes` informa la memoria del proceso
ADA mientras ese MCP está activo, no una asignación física exclusiva.

## Health Doctor y diagnóstico

El servicio `HealthDoctor` (`ada/interfaces/web/doctor.py`) audita 7 áreas críticas del sistema:

1. **Motor Ollama LLM**: Disponibilidad del socket y latencia HTTP.
2. **Modelos Instalados**: Existencia de al menos un modelo descargado.
3. **Núcleo ADA**: Estado del orquestador y router.
4. **Subconjunto MCP**: Salud y disponibilidad de los servidores de herramientas.
5. **Memoria SQLite**: Integridad de tablas e índices en `ada/memory.db`.
6. **Recursos de Hardware**: Uso de RAM, throttling de CPU y VRAM.
7. **Servicio Telegram Bot**: Conexión del bot y estado de long-polling.


## Auto-remediación

Si algún subsistema se encuentra degradado o detenido, el botón **"Auto-reparar Todo"** del Dashboard ejecuta secuencialmente las acciones de recuperación:
- Iniciar el servicio local de Ollama.
- Levantar los servidores MCP caídos.
- Re-inicializar tablas de memoria.
- Descargar modelos de VRAM si la memoria está saturada.


## Respaldos de la base de datos

Para respaldar tu historial de conversaciones, recetas y datos personales:

```bash
# Copia directa segura de SQLite
cp ada/memory.db ~/Desktop/ada_backup_$(date +%Y%m%d).db
```

## Alertas del Sarmiento con presencia

ADA incluye el MCP `transport` con la tool `transport.get_status` y una regla opcional para consultar el Sarmiento a las 13:00
cuando existe una señal de presencia válida en `work`. La función está desactivada por defecto.

1. Configurá el token de la API de Transporte BA fuera de Git:

```bash
export ADA_TRANSPORT_API_TOKEN="..."
```

2. Activá `triggers.cron.sarmiento_status.enabled` y definí `chat_id` en `ada/config.json`.
3. Desde un teléfono, Tasker, Home Assistant o una geofence autenticada, enviá la presencia por el endpoint privado:

```bash
curl -X POST http://127.0.0.1:5005/api/events \
  -H 'Content-Type: application/json' \
  -H "X-ADA-Event-Token: $ADA_EVENT_TOKEN" \
  -d '{"topic":"presence.updated","payload":{"location":"work","active":true,"ttl_seconds":7200,"source":"phone-geofence"}}'
```

La presencia caduca automáticamente. Tailscale puede proteger el acceso entre el teléfono y ADA, pero no reemplaza la
geofence ni determina por sí solo la ubicación física.

## Contexto y memoria acotados

`ContextManager` construye paquetes de contexto por sesión con presupuesto por rol
(`router`, `chat`, `coding`, `reasoning` y `tools`). Recupera sólo memoria relevante,
conversación reciente y resúmenes persistentes en SQLite; el cálculo de tokens es una
estimación conservadora cuando no hay tokenizer específico del modelo.

## Actualizaciones seguras

El `UpdateManager` está integrado al daemon, pero `update.enabled` y `update.auto_pull`
son `false` por defecto. Al habilitarlo, sólo acepta un fast-forward sobre un worktree
limpio y usa `git pull --ff-only`; nunca ejecuta `reset --hard` ni borra archivos.
Cuando `update.restart_on_update` está activo, envía antes del reinicio un aviso de
Telegram con fecha, hora, SHA completo y mensaje del commit. Configurá el destinatario
en `update.telegram_chat_id` (y el token mediante la configuración habitual de Telegram).
El estado queda en el `state_path` configurado.
