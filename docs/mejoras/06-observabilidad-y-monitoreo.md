# 📈 06. Observabilidad y Monitoreo

## Estado de Implementación

| ID | Mejora / Corrección | Estado | Commit |
|---|---|---|---|
| OBS-01 | Exposición de métricas en formato estándar Prometheus (`/metrics`) | ✅ Implementado | `5e34825` |
| OBS-02 | Contenedores de monitoreo listos con `docker-compose.monitoring.yml` | ✅ Implementado | `5e34825` |
| OBS-03 | Trazabilidad en tiempo real de actividad del agente (`/api/core/state`) | ✅ Implementado | `4db33d3` |
| OBS-04 | Tablero de auditoría de operaciones en base de datos (`/api/audit`) | ✅ Implementado | `4db33d3` |
| CI-01  | Corrección de rutas en `.github/workflows/ci.yml` para tests automáticos | ✅ Implementado | `620070c` |

---

## Detalle de Métricas Principales

- `ada_requests_total`: Contador de peticiones por endpoint, método HTTP y código de respuesta.
- `ada_request_duration_seconds`: Histograma de latencia por endpoint.
- `ada_capability_calls_total`: Contador de herramientas MCP ejecutadas.
- `ada_hardware_*`: Uso de CPU, memoria y VRAM registrado en Prometheus.
