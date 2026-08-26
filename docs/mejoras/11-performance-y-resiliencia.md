# 11. Performance, concurrencia y resiliencia del runtime

## Objetivo

Reducir latencia y contención bajo concurrencia, aprovechar correctamente SQLite WAL y evitar que status, chat, SSE o healthchecks bloqueen recursos compartidos.

## Estado de implementación

| ID | Mejora / Corrección | Estado | Impacto | Esfuerzo |
|---|---|---|---|---|
| PERF-01 | Conexión SQLite por thread y lock exclusivo de escritura | 🔴 Pendiente | Alto | Medio |
| PERF-02 | Cache TTL de `hardware_profile()` | 🔴 Pendiente | Alto | Bajo |
| PERF-03 | Cachear e invalidar la policy de modelos | 🟠 Pendiente | Medio-alto | Bajo |
| PERF-04 | Reutilizar clientes HTTP/proveedores | 🟠 Pendiente | Medio | Bajo-medio |
| PERF-05 | Streaming real de tokens hacia SSE | 🟠 Pendiente | Alto en percepción | Medio |
| PERF-06 | Servidor productivo y `/api/chat` fuera del thread de request | 🟠 Pendiente | Medio-alto | Medio |
| PERF-07 | SSE basado en pub/sub, `Queue` o `Condition` | 🟡 Pendiente | Medio | Medio |
| PERF-08 | HealthDoctor con TTL y chequeos paralelos | 🟡 Pendiente | Medio | Bajo |
| PERF-09 | LRU/TTL para `session_states` y lazy-load del historial | 🟠 Pendiente | Medio | Medio |
| PERF-10 | No mantener locks MCP durante sleeps/restarts | 🟢 Pendiente | Bajo-medio | Bajo |

## Orden recomendado

1. Medir `/api/chat` y `/api/ollama/status` con las métricas existentes, y complementar con profiling puntual.
2. Separar conexiones SQLite por thread; mantener un lock únicamente para escritores y dejar que WAL permita lecturas concurrentes.
3. Cachear hardware y policy, invalidando cuando cambie la configuración o se ejecute `reload()`.
4. Habilitar streaming y reutilización de clientes HTTP.
5. Corregir el modelo de ejecución del servidor, SSE y sesiones.

## Problemas observados

- Una conexión SQLite compartida y un `RLock` global serializan lecturas y escrituras; algunos reads además se ejecutan sin lock.
- `hardware_profile()` puede importar Torch y ejecutar `nvidia-smi` repetidamente en rutas calientes.
- El chat no-stream puede bloquear el worker hasta 15 minutos; el servidor de desarrollo no es adecuado para carga sostenida.
- El SSE usa polling con `time.sleep(0.5)`, reteniendo un thread por conexión.
- `session_states` no tiene límite ni expiración y puede conservar hasta 1000 mensajes por sesión.
- Las llamadas a proveedores no tienen retry/backoff consistente y recrean clientes/conexiones.

## Criterios de aceptación

- Pruebas de concurrencia sin uso recursivo de cursores ni corrupción de datos.
- Presupuesto y TTL documentados para cachés; invalidación cubierta por tests.
- Time-to-first-token medible en streaming y ausencia de polling fijo en SSE.
- Las sesiones inactivas se evacúan y los endpoints de diagnóstico no repiten I/O caro innecesariamente.
