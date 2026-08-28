# Observabilidad y métricas

La observabilidad es una capacidad transversal, no una tarea posterior. La
información debe permitir decidir qué modelo, estrategia, filtro o integración
conviene mantener.

## Señales

- **Métricas:** Micrometer + Actuator, exportación Prometheus.
- **Logs:** JSON estructurado con `traceId`, `spanId`, `correlationId`, contexto,
  caso de uso, resultado y duración.
- **Trazas:** OpenTelemetry cuando exista backend configurado.
- **Auditoría:** SQLite para decisiones, acciones, confirmaciones y errores de
  negocio; no reemplaza logs técnicos.

## Métricas mínimas

Todas deben incluir solo labels de cardinalidad controlada:

- `ada_requests_total{context,use_case,outcome}`
- `ada_request_duration_seconds{context,use_case}`
- `ada_llm_requests_total{provider,model,outcome}`
- `ada_llm_duration_seconds{provider,model}`
- `ada_llm_tokens_total{provider,model,direction}`
- `ada_llm_cost_estimated_total{provider,model,currency}`
- `ada_strategy_selected_total{context,strategy,outcome}`
- `ada_filter_applied_total{context,filter}`
- `ada_external_calls_total{system,operation,outcome}`
- `ada_persistence_operations_total{store,operation,outcome}`
- `ada_audit_events_total{event_type,outcome}`

No se usan prompts, IDs de usuario, texto libre ni excepciones completas como
labels. Esos detalles pertenecen a logs redactados o auditoría controlada.

## Decisiones y calidad de datos

Cada invocación LLM debe capturar, si el proveedor lo informa: modelo pedido y
modelo efectivo, tokens de entrada/salida, latencia, reintentos, timeout,
estimación de costo, filtros aplicados, estrategia elegida y motivo de fallback.
Los contadores deben ser monotónicos y las duraciones histogramas.

La ausencia de datos del proveedor se representa como `unknown`, nunca se
imputa silenciosamente.

## Duración inmediata de una petición

Los contadores históricos (`*_total`, `*_sum`, `*_count`) deben consultarse con
`rate` o `increase` para una ventana temporal. No representan la última
ejecución y pueden conservar actividad mientras exista una ventana de datos.

Para diagnóstico inmediato ADA expone gauges que no esperan a que expire una
ventana de Micrometer:

- `ada_request_last_duration_seconds`: duración completa de la última petición,
  desde el inicio del flujo hasta su finalización o fallo.
- `ada_requests_active`: peticiones actualmente en curso; vuelve a cero al
  finalizar cada ejecución.
- `ada_pipeline_stage_last_duration_seconds{stage="..."}`: duración de la
  última ejecución de cada etapa (`filtering_command`, `context_creation`,
  `model_invoke` y `tool_invoke`).

El dashboard debe mostrar estos gauges separados de las tasas históricas para
que una decisión operativa no dependa de esperar que expire una ventana de
agregación.

## Memoria por componente

La sección de recursos muestra memoria RSS detectada en el host para `ada`,
`litellm`, `ollama`, `telegram`, `prometheus` y `grafana` mediante el exporter
local `scripts/monitoring/host-resource-exporter.py`. Prometheus lo consulta
como `ada_host_component_memory_bytes{component}` a través de
`host.docker.internal`, porque un proceso dentro del contenedor no puede ver
correctamente los procesos del host. El consumo de los modelos cargados se
expone como `ada_host_ollama_model_memory_bytes{model}` consultando Ollama; si
Ollama no informa modelos activos, la serie queda en `unknown` y no se inventa
una atribución. La memoria global se conserva en
`ada_host_system_memory_bytes{state="total|used|available"}`. El exporter no
publica command lines, prompts, credenciales ni datos personales.

## Persistencia de Grafana

Grafana se ejecuta en Docker con una versión fijada en `compose.yaml` y usa el
volumen nombrado `grafana-data` para conservar usuarios, configuración y
dashboards entre recreaciones del contenedor. El datasource de Prometheus y el
dashboard operativo se provisionan desde `monitoring/grafana`, por lo que una
instalación nueva o un volumen vacío puede reconstruirse sin depender de una
edición manual en la UI. No se debe ejecutar `docker compose down -v` salvo que
se quiera eliminar explícitamente esos datos.

## Permisos del volumen de datos

La imagen ejecuta ADA con el usuario no root `ada` (UID/GID `10001`). En una
instalación nueva, el directorio configurado en `ADA_DATA_DIR` debe existir y
ser escribible por ese UID/GID, o se deben definir explícitamente
`ADA_CONTAINER_UID` y `ADA_CONTAINER_GID` en `deploy/.env`. El primer arranque
con una ruta nueva debe validarse revisando `/actuator/health` y los logs del
servicio.
