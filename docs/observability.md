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
