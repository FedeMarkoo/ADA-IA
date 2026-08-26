# 11. Performance, concurrencia y resiliencia del runtime

## Objetivo y regla de trabajo

Reducir latencia y contención bajo concurrencia, aprovechar correctamente SQLite WAL y evitar que status, chat, SSE o healthchecks bloqueen recursos compartidos.

La regla de oro es medir antes de optimizar. ADA ya expone métricas Prometheus y timing por operación; conviene complementar con `py-spy` o `cProfile` sobre `/api/chat` y `/api/ollama/status` para confirmar dónde está el tiempo real.

## Estado de implementación

| ID | Mejora / Corrección | Estado | Impacto | Esfuerzo |
|---|---|---|---|---|
| PERF-01 | Conexión SQLite por thread y lock exclusivo de escritura | ✅ Implementado | Alto | Medio |
| PERF-02 | Cache TTL de `hardware_profile()` | ✅ Implementado | Alto | Bajo |
| PERF-03 | Cachear e invalidar la policy de modelos | ✅ Implementado | Medio-alto | Bajo |
| PERF-04 | Reutilizar clientes HTTP/proveedores | ✅ Implementado | Medio | Bajo-medio |
| PERF-05 | Streaming real de tokens hacia SSE | 🟠 Pendiente | Alto en percepción | Medio |
| PERF-06 | Servidor productivo y `/api/chat` fuera del thread de request | ✅ Implementado | Medio-alto | Medio |
| PERF-07 | SSE basado en pub/sub, `Queue` o `Condition` | 🟡 Pendiente | Medio | Medio |
| PERF-08 | HealthDoctor con TTL y chequeos paralelos | ✅ Implementado | Medio | Bajo |
| PERF-09 | LRU/TTL para `session_states` y lazy-load del historial | ✅ Implementado | Medio | Medio |
| PERF-10 | No mantener locks MCP durante sleeps/restarts | ✅ Implementado | Bajo-medio | Bajo |

## Priorización

| Orden | Mejora | Por qué |
|---|---|---|
| 1 | SQLite por thread | Destraba la persistencia completa y permite lectores concurrentes reales |
| 2 | Cachear hardware | Saca `nvidia-smi` y Torch del hot path con poco esfuerzo |
| 3 | Streaming | Reduce mucho el time-to-first-token y mejora la sensación del chat |
| 4 | Cachear policy | Evita recalcular catálogo + hardware por rol/request |
| 5 | Servidor productivo y executor | Evita bloquear workers bajo concurrencia |
| 6 | Clientes HTTP persistentes | Evita handshakes y unifica retries/fallbacks |
| 7 | SSE sin polling | Escala mejor con varias pestañas |
| 8 | HealthDoctor paralelo | Reduce la latencia del diagnóstico |
| 9 | Locks MCP fuera de sleeps | Evita congelar operaciones durante reinicios |

Si hubiera que implementar solamente tres: `PERF-02`, `PERF-01` y `PERF-05`.

## PERF-01: SQLite por thread

### Problema

Existe una sola conexión compartida protegida por un `RLock` global. Eso serializa todas las lecturas y escrituras: aunque haya ocho workers de chat, la persistencia avanza de a uno. WAL ya está activado, pero se desperdicia su beneficio principal: permitir lectores concurrentes mientras escribe otro thread.

Además, algunas lecturas calientes —por ejemplo `router_actions` y `prompt_template`— se hacen sin tomar el lock. Con chat, daemon y refiner en paralelo, esto puede producir `Recursive use of cursors` u otros problemas de acceso concurrente.

### Diseño propuesto

```python
class Memory:
    def __init__(self, db_path, ...):
        self._local = threading.local()
        self._write_lock = threading.Lock()  # SQLite: un solo escritor

    def _conn(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return conn

    # lecturas: sin lock global; WAL permite concurrencia
    # escrituras: with self._write_lock
```

Cada thread debe obtener su propia conexión y cerrar la conexión al terminar su ciclo de vida cuando el runtime lo permita. Las transacciones de escritura deben ser cortas y estar protegidas por el lock exclusivo de escritor.

## PERF-02 y PERF-03: hardware y policy

`hardware_profile()` importa Torch y puede ejecutar `nvidia-smi`, con un coste de hasta aproximadamente 1,5 segundos. Se invoca en cada `/api/ollama/status` y dentro de `effective_policy()` por cada rol.

Un TTL de 30–60 segundos evita repetir un dato que normalmente no cambia entre requests:

```python
_hw_cache = {"at": 0.0, "val": None}

def hardware_profile():
    now = time.monotonic()
    if _hw_cache["val"] and now - _hw_cache["at"] < 30:
        return _hw_cache["val"]
    value = _compute_hardware_profile()
    _hw_cache.update(at=now, val=value)
    return value
```

La policy automática también debe cachearse y recalcularse únicamente cuando cambie la configuración, el catálogo o se ejecute `reload()`. Esto evita que `runtime_status()` recalcule lo mismo tres veces y que `_model()` vuelva a escanear hardware y catálogo para cada rol.

## PERF-04: clientes y conexiones HTTP

`_call_openai()` crea un cliente `OpenAI()` nuevo en cada llamada. Los demás proveedores usan `urllib.urlopen` aislado, sin keep-alive, retry/backoff consistente ni reutilización de conexiones TCP/TLS.

La alternativa mínima es cachear clientes por `(provider, base_url)` y usar una `requests.Session` o `httpx.Client` persistente. LiteLLM puede centralizar proveedores, conexiones, retries, fallbacks y streaming, pero debe introducirse detrás de la abstracción existente y validarse contra la política de modelos actual.

## PERF-05: streaming real

Los payloads actuales envían `"stream": false`, aunque el frontend ya tiene `/api/chat/stream` y SSE. El streaming no necesariamente reduce el tiempo total, pero sí lleva el primer token al usuario casi inmediatamente y evita esperar toda la respuesta para empezar a renderizar.

El flujo propuesto es:

```text
Ollama/OpenAI stream
        ↓
ModelManager: chunks normalizados
        ↓
ChatService
        ↓
/api/chat/stream → SSE → dashboard
```

Debe contemplar eventos de inicio, chunks, finalización, error y cancelación, además de liberar correctamente el generador y la sesión HTTP.

## PERF-06 y PERF-07: servidor, chat y SSE

El `/api/chat` no-stream ejecuta `handle()` sincrónicamente en el thread del request y puede bloquearlo hasta 900 segundos. El stream ya delega al executor. Además, Werkzeug con `threaded=True` es un servidor de desarrollo y no debería sostener carga de producción.

Opciones: usar Waitress en WSGI —simple y compatible con Windows— o consolidar el servicio ASGI existente, que ya usa `run_in_executor`. El endpoint no-stream debe delegar al mismo `chat_executor` que el stream.

`activity_stream` y `debug_events_stream` hacen `time.sleep(0.5)` dentro de un loop. Eso retiene un thread por pestaña y puede agotar el pool. La solución preferida es publicar eventos mediante `Queue`/`Condition` y despertar solamente cuando cambie el estado; en ASGI, una corrutina async evita un thread dedicado por conexión.

## PERF-08 a PERF-10: diagnóstico, sesiones y MCP

- `HealthDoctor` se recrea en cada `/api/healthcheck` y ejecuta ocho checks secuenciales, varios con I/O bloqueante de red. Un cache TTL de 5–10 segundos y un `ThreadPoolExecutor` para checks independientes reduce la latencia desde la suma de todos los checks al más lento.
- `session_states` crece sin límite. Un cliente sin cookies puede crear una sesión por request y cada estado conserva hasta 1000 mensajes. Debe existir LRU/TTL, tope de sesiones, lazy-load desde SQLite y limpieza de estados inactivos.
- `restart_server` y `restart_all_servers` mantienen el `RLock` del MCP durante `time.sleep(0.1)`. Hay que capturar nombres/estado bajo lock, liberar, hacer sleeps y reinicios, y volver a adquirirlo solo para publicar el resultado.

## Criterios de aceptación

- Pruebas de concurrencia sin uso recursivo de cursores ni corrupción de datos.
- Benchmarks antes/después para `/api/chat`, `/api/ollama/status` y `/api/healthcheck`.
- TTLs, presupuestos e invalidación de cachés documentados y cubiertos por tests.
- Time-to-first-token medible en streaming y ausencia de polling fijo en SSE.
- Las sesiones inactivas se evacúan y los endpoints de diagnóstico no repiten I/O caro innecesariamente.
