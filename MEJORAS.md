# 🔬 Code Review Exhaustivo — ADA-IA v2

> Revisión completa de todos los módulos del proyecto.
> Cubre: `memory_refiner`, `model_manager`, `agent`, `sqlite`, `router`, `config`, `web_chat`, `folder_resolver`, `triggers`, `autonomy`, `daemon`, `cli`, `scheduler`, `capabilities/registry`, `prompts`, `policy`, `coordinator`, `ollama`, `resources`, `responses`, `observability`, `i18n`, `watchers`, `duplicates`.
> Fecha: 2026-08-22 | Versión: 2 (análisis profundo)

---

## Índice

1. [Bugs Críticos](#1-bugs-críticos)
2. [Bugs Importantes](#2-bugs-importantes)
3. [Seguridad](#3-seguridad)
4. [Concurrencia y Threading](#4-concurrencia-y-threading)
5. [Rendimiento y Escalabilidad](#5-rendimiento-y-escalabilidad)
6. [Robustez y Manejo de Errores](#6-robustez-y-manejo-de-errores)
7. [Calidad de Código y DRY](#7-calidad-de-código-y-dry)
8. [Arquitectura](#8-arquitectura)
9. [Testing](#9-testing)
10. [Checklist](#-checklist-de-acción)

---

## 1. Bugs Críticos

### [BUG-C1] `choose()` — lógica de privacidad y complejidad es código muerto
**Archivo:** `model_manager.py`, líneas ~514–519

```python
# Orden actual (ROTO):
if self.provider in available and available[self.provider]:
    return self.provider        # ← retorna SIEMPRE que provider esté activo
if privacy == "high" and available.get(self.provider):
    return self.provider        # ← NUNCA SE ALCANZA
if complexity <= int(...) and available.get(self.provider):
    return self.provider        # ← NUNCA SE ALCANZA
```

La intención es: si `privacy=high`, usar modelo local; si `complexity` es baja, preferir local. Ninguna de las dos condiciones funciona porque la primera condición es un superset de ambas.

**Fix:** Invertir el orden de prioridad.
```python
if privacy == "high" and available.get(self.provider):
    return self.provider
if requested in available and available[requested]:
    return requested
if complexity <= int(self.config.get("local_max_complexity", 5)) and available.get(self.provider):
    return self.provider
if self.provider in available and available[self.provider]:
    return self.provider
```

---

### [BUG-C2] Deadlock potencial entre `MemoryRefiner._lock` y `Memory._lock`
**Archivo:** `memory_refiner.py`, línea ~88

`refine_cycle` adquiere `self._lock` y dentro llama a métodos de `Memory` que adquieren `Memory._lock`. Si en otro hilo, un método de `Memory` está corriendo y necesita notificar al refiner (o simplemente se dan en orden inverso), hay deadlock clásico.

**Fix:** Liberar `self._lock` antes de llamar a `Memory`. Solo usarlo para proteger `_last_run`.

---

### [BUG-C3] `daemon.py` — bucle infinito sin señal de shutdown
**Archivo:** `daemon.py`, líneas 33–45

```python
while True:
    for watcher in watchers:
        watcher.scan()
    scheduler.run_once()
    ...
    time.sleep(...)
```

No hay manejo de `SIGTERM`/`SIGINT` → el proceso no puede detenerse limpiamente. El backup que se estaba ejecutando puede quedar corrompido y el archivo WAL de SQLite sin checkpoint.

**Fix:**
```python
import signal

stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
signal.signal(signal.SIGINT, lambda *_: stop.set())

while not stop.is_set():
    ...
    stop.wait(timeout=max(0.1, float(config.get("watch_interval", 5))))
```

---

### [BUG-C4] `FolderWatcher.scan()` carga todo el árbol en RAM
**Archivo:** `watchers.py`, línea 19

```python
current = {str(path) for path in paths if path.is_file() ...}
```

Con `recursive=True` (por defecto), en carpetas grandes (DCIM, Google Drive) este set puede contener decenas de miles de entradas. Además `self._seen` nunca se poda → memory leak proporcional al número total de archivos vistos.

**Fix:** Limitar `_seen` a un conjunto circular o usar timestamps del sistema de archivos en lugar de listas de paths.

---

### [BUG-C5] `autonomy.py` — acción de alta prioridad puede ejecutarse sin confirmación si `auto_confirm` es `True` y la regla dice `auto_execute`
**Archivo:** `autonomy.py`, línea 32

```python
auto_execute = bool(rule.get("auto_execute", False)) and not plan.high_risk()
task = {
    ...
    "confirm": bool(rule.get("auto_confirm", False)) if auto_execute else None,
}
```

Si `auto_execute=True` y `auto_confirm=True`, el agente ejecutará la acción incluso si es de alto riesgo — `plan.high_risk()` bloquea `auto_execute`, pero si el plan no clasifica correctamente una acción como riesgosa, se ejecuta sin confirmación.

El problema más concreto: `action_name not in self.agent.skills` retorna `{"ok": False, ...}` sin auditar el intento. Una acción mal configurada no deja rastro en `audit_log`.

**Fix:** Agregar `record_audit` también cuando `action_name not in self.agent.skills`.

---

## 2. Bugs Importantes

### [BUG-I1] `cli.py` — `mem` se usa fuera de su scope de definición
**Archivo:** `cli.py`, línea 227

```python
elif args.cmd == "backup":
    print(mem.backup_to(args.path))  # ← mem solo se define si cmd es "index", "suggest" etc.
```

Si el usuario ejecuta `ada backup --path /tmp/backup.db` directamente (sin pasar antes por `index` o `suggest`), `mem` puede estar indefinido. En Python esto lanza `NameError`.

**Fix:** Definir `mem` antes del bloque de comandos, o dentro del bloque `backup`.

---

### [BUG-I2] `folder_resolver.py` — `_children` lanza subproceso `ls` sin sanitizar el path
**Archivo:** `folder_resolver.py`, líneas 63–64

```python
process = subprocess.Popen(
    ["ls", "-1A", "--quoting-style=literal", "--", str(parent)],
    ...
)
```

El `--` antes del path protege contra paths que empiecen con `-`. Sin embargo, si `parent` es una cadena que llega de la configuración del usuario y contiene bytes inválidos en el locale, el decodificado en línea 80 usa `errors="replace"` — correcto — pero podría producir resultados silenciosamente incorrectos.

Más importante: el path de la carpeta viene de `self._base()` → `self.config.get("base_dir")`. Si `base_dir` contiene espacios y el shell lo interpreta (lo cual no ocurre en `Popen` con lista de args), está bien. Pero hay un caso problemático: cuando `_is_directory` usa `["test", "-d", str(path)]`, este binario `test` no existe en todos los sistemas (macOS sí, Linux con dash puede diferir). Si `test` no está en `PATH`, lanza `OSError` que se silencia.

**Fix:** Usar `Path.is_dir()` con timeout en un thread daemon en lugar de un subproceso.

---

### [BUG-I3] `triggers.py` — `_persist_enabled` puede corromper el config al escribir
**Archivo:** `triggers.py`, líneas 172–188

La escritura usa un archivo temporal con `os.replace()` — correcto. Pero:
```python
saved["telegram"]["enabled"] = bool(enabled)
temporary.write_text(json.dumps(saved, ...), ...)
os.replace(temporary, self.config_path)
```

Si el JSON en `self.config_path` tiene valores que `json.loads` no puede parsear (por ejemplo, porque el usuario lo editó a mano y tiene un comentario JavaScript `//`), `json.loads` lanza `ValueError` que sí está capturado, pero el bloque `except` no hace `return` — el código continúa al `temporary.write_text` con `saved = {}` (el default de la cláusula `except`... en realidad no, porque el except atrapa solo `json.loads` en un `if` separado).

Revisando la lógica exactamente:
```python
saved = json.loads(...) if self.config_path.is_file() else {}
```
Si `json.loads` falla, es ValueError que está en el except → saved no se asigna en el `try` pero no hay `try/except` aquí. El `except` en línea 188 atrapa el bloque completo. Entonces `saved` puede no estar definido si la excepción ocurre en `json.loads` antes de asignarse. → `NameError` potencial.

**Fix:** Inicializar `saved = {}` antes del bloque.

---

### [BUG-I4] `memory_refiner.py` — variable `low` definida pero nunca usada
**Archivos:** `memory_refiner.py`, líneas ~169, ~187

`low = text.lower()` se define pero el `re.search` corre sobre `text` con `re.IGNORECASE`. La variable es dead code que confunde al lector.

---

### [BUG-I5] `memory_refiner.py` — colisión de claves de hechos aprendidos
**Archivo:** `memory_refiner.py`, línea ~148

Nombre: `f"learned_pref_{int(time.time())}_{count}"`. Si dos sesiones se procesan en el mismo segundo, `count` se resetea a 0 en cada una → mismo nombre → sobrescritura silenciosa en `add_knowledge`.

**Fix:** `f"learned_pref_{int(time.time_ns())}"` o incluir session id.

---

### [BUG-I6] `web_chat.py` — greeting hardcodeado ignora el catálogo de idiomas
**Archivo:** `web_chat.py`, línea ~306

```python
reply = "ADA versión 0.1.0"
```
La versión está hardcodeada como string. Si se sube la versión en `pyproject.toml`, este string no se actualiza. Debería importar `importlib.metadata` o usar una constante.

---

### [BUG-I7] `sqlite.py` — `knowledge()` y `search_text()` cargan hasta 10.000 filas sin FTS
**Archivo:** `sqlite.py`, líneas 520, 558

Sin FTS disponible, se hace `fetchall()` de 10.000 filas y se filtra en Python. En entornos con muchos hechos aprendidos, esto consume mucha RAM y es lento.

---

### [BUG-I8] `sqlite.py` — `_apply_migrations` sin commit entre steps
**Archivo:** `sqlite.py`, línea ~194

Si el proceso muere durante una migración, `user_version` no queda actualizado y la migración se repite al reiniciar (puede ejecutar `ALTER TABLE` dos veces).

---

### [BUG-I9] `model_manager.py` — `reload()` duplica `__init__` — riesgo de estado inconsistente
**Archivo:** `model_manager.py`, línea ~83

Si se agrega un campo al `__init__`, `reload()` queda desincronizado silenciosamente.

---

### [BUG-I10] `capabilities/registry.py` — `_LOADED_SPECS` es un dict global mutable compartido entre llamadas
**Archivo:** `registry.py`, línea 39

```python
_LOADED_SPECS: Dict[str, Dict[str, Any]] = {}
```

Este dict es estado global. Si `load_capabilities()` se llama desde dos threads simultáneamente (por ejemplo durante el startup del servidor), `_LOADED_SPECS.clear()` y el relleno subsecuente pueden producir una vista inconsistente.

**Fix:** Hacer `_LOADED_SPECS` local a la función o agregar un lock de módulo.

---

## 3. Seguridad

### [SEC-1] `model_manager._call_gemini` — API key en URL → aparece en tracebacks y logs
**Archivo:** `model_manager.py`, línea ~659

```python
url = "https://generativelanguage.googleapis.com/.../generateContent?key=" + urllib.parse.quote(self.gemini_key)
```

Cualquier `urllib.error.HTTPError` o excepción de red imprime la URL completa con la key en el traceback. Los logs de debug también la capturan si se loguea la request.

**Fix:** Pasar por header `x-goog-api-key` en lugar de query param.

```python
request = urllib.request.Request(url, ...)
request.add_header("x-goog-api-key", self.gemini_key)
```

---

### [SEC-2] `sqlite.py` — f-strings en SQL de migración (patrón inseguro)
**Archivo:** `sqlite.py`, línea ~84

```python
self.conn.execute(f"SELECT id, {column} FROM {table}")
```

Hoy los valores son hardcodeados. Pero si en el futuro `table`/`column` fueran configurables por el usuario, sería SQL injection directo. Agregar whitelist explícita.

```python
ALLOWED_MIGRATION_TABLES = {"memories", "tasks", "conversation_messages"}
assert table in ALLOWED_MIGRATION_TABLES, f"Tabla no autorizada: {table}"
```

---

### [SEC-3] `triggers.py` — token de Telegram se lee y loguea en `_log_tail`
**Archivo:** `triggers.py`, línea 161–163

```python
token = self._resolve_token()
if token:
    values = [line.replace(token, "***") for line in values]
```

Esto redacta el token en el tail del log. Sin embargo, `_resolve_token` puede lanzar excepciones si el módulo de Telegram no está instalado. Si falla, el token queda sin redactar en los logs que se envían al frontend.

**Fix:** Envolver `_resolve_token` en try/except al usarlo en `_log_tail`.

---

### [SEC-4] `autonomy.py` — `path_prefix` comparado con `startswith` — bypass trivial
**Archivo:** `autonomy.py`, línea 66

```python
if prefix and not str(payload.get("path", "")).startswith(str(prefix)):
    return False
```

Si `prefix = "/home/user/Photos"`, la ruta `/home/user/Photos_evil` pasa el filtro. Debe usar comparación de Path normalizada.

```python
from pathlib import Path
if prefix:
    try:
        Path(payload["path"]).resolve().relative_to(Path(prefix).resolve())
    except ValueError:
        return False
```

---

### [SEC-5] `policy.py` — `validate_paths` acepta `None` como path válido
**Archivo:** `policy.py`, línea 30

```python
invalid = [str(value) for value in values if value and not self.path_allowed(value)]
```

El filtro `if value` descarta `None`, pero `path_allowed(None)` haría `Path(os.path.expanduser("None")).resolve()` → un path válido en el FS. No es explotable directamente, pero es inconsistente.

---

### [SEC-6] `model_manager._call_groq` / `_call_gemini` no manejan `HTTPError`
Respuestas de error de la API (401, 429, 500) llegan sin manejar → el cuerpo de error (que puede contener metadata del request, incluyendo el prompt) llega completo al log de error.

---

## 4. Concurrencia y Threading

### [THREAD-1] `_call_gpt4all` — inicialización de `self._gpt4all` sin lock
**Archivo:** `model_manager.py`, línea ~695

```python
if self._gpt4all is None:
    from gpt4all import GPT4All
    self._gpt4all = GPT4All(...)
```

Si dos threads llegan simultáneamente con `self._gpt4all is None`, se crean dos instancias → estado corrupto.

---

### [THREAD-2] `TriggerManager.stop()` llama `self.telegram_status()` dentro del lock, que a su vez llama `_read_state()` — posible reentrada con `RLock` (aceptable) pero llama a `self.stop()` → recursión potencial si el watchdog está corriendo
**Archivo:** `triggers.py`, líneas 292–313

`stop()` llama `self.telegram_status()` dentro de `with self._lock`. `telegram_status()` también adquiere `with self._lock` — como es `RLock` esto está bien. Pero si `reconcile()` (llamado por el watchdog) llama `self.start()` mientras `stop()` está corriendo, hay una condición de carrera: el watchdog puede reiniciar el proceso que `stop()` acaba de terminar, si el watchdog tick ocurre en la ventana entre `process.terminate()` y la escritura del nuevo state.

**Fix:** El watchdog debería verificar `desired_state == "stopped"` antes de reiniciar, lo cual ya hace — pero el TTL de 10s en `_last_start_attempt` puede ser insuficiente.

---

### [THREAD-3] `Scheduler.run_forever()` — stop event, pero `run_once()` no es re-entrante
**Archivo:** `scheduler.py`, líneas 46–53

Si `run_forever()` corre en un thread y otro thread llama `run_once()` directamente, ambos pueden reclamar el mismo evento de la DB (`claim_events` tiene su propio lock en SQLite, así que no hay doble-claim), pero sí pueden interferir en `ack`/`retry`/`fail` del mismo event_id.

---

### [THREAD-4] `LocalModelRuntime.ensure_ready()` doble-check sin lock externo
**Archivo:** `ollama.py`, líneas 132–136

```python
def ensure_ready(self):
    with self._lock:
        status = self.status()
        if status.available or not self.auto_start:
            return status
        return self.start()
```

`self.start()` también adquiere `self._lock`. Como es `threading.Lock` (no `RLock`), `start()` dentro de `ensure_ready()` va a deadlock si `start()` intenta adquirir `self._lock`.

**Verificar:** Si `start()` comienza con `with self._lock:` y `ensure_ready()` ya lo tiene → deadlock inmediato.

---

## 5. Rendimiento y Escalabilidad

### [PERF-1] `FolderWatcher` — `rglob("*")` en Google Drive monta en el thread principal
**Archivo:** `watchers.py`, línea 18

```python
paths = self.folder.rglob("*") if self.recursive else self.folder.iterdir()
current = {str(path) for path in paths if path.is_file() ...}
```

`rglob` en Python es síncrono. Si `self.folder` es un montaje de Google Drive (GVFS), `rglob` puede bloquear el loop del daemon por segundos o minutos mientras el kernel hace I/O de red.

`FolderResolver` ya usa subprocesos con timeout para exactamente este motivo. `FolderWatcher` debería hacer lo mismo.

---

### [PERF-2] `prompts.py` — `memory.knowledge()` + `memory.find_procedures()` en cada request
**Archivo:** `prompts.py`, líneas 36, 41

Para cada prompt del usuario se hacen dos búsquedas en SQLite (potencialmente lentas sin FTS). Con muchos hechos y procedimientos, esto puede agregar 100–500ms por request.

**Mejora:** Cachear procedimientos frecuentes en RAM con TTL corto (30s).

---

### [PERF-3] `capability_catalog()` llama `capability_specs()` que llama `load_capabilities()` — recarga todos los módulos del disco en cada llamada
**Archivo:** `registry.py`, líneas 71–73

```python
def capability_specs():
    capabilities = load_capabilities()  # ← rglob + importlib en cada llamada
```

Si `capability_catalog()` se llama desde el dashboard de estado, se recargan todos los módulos de capability en cada request.

**Fix:** Cachear el resultado con un timestamp y recargar solo si algún archivo cambió.

---

### [PERF-4] `Observability.Metrics._timings` crece sin bound por métrica
**Archivo:** `observability.py`, línea 26–28

```python
values = self._timings[self._key(name, tags)]
values.append(round(float(seconds), 6))
del values[:-1000]
```

`del values[:-1000]` es O(N) en una lista Python — crea un nuevo slice y garbage-collects el resto. Para listas frecuentes (llamadas a modelos), esto ocurre en cada `observe()`. Usar `collections.deque(maxlen=1000)` es O(1) para ambas operaciones.

---

### [PERF-5] `sqlite.py` — `conversation()` retorna hasta 1000 mensajes completos en cada sesión
**Archivo:** `sqlite.py`, línea 757

```python
rows = self.conn.execute(
    "SELECT id, created_at, role, text, model FROM conversation_messages "
    "WHERE session=? ORDER BY id DESC LIMIT ?",
    (session, limit),  # limit=1000
).fetchall()
```

Para sesiones largas de Telegram, 1000 mensajes pueden ser MB de texto. Solo se usan los últimos 8 en `web_chat._conversation_context()`. Se debería pasar el limit real como parámetro.

---

## 6. Robustez y Manejo de Errores

### [ROB-1] `daemon.py` — `watcher.scan()` puede lanzar excepciones no capturadas
**Archivo:** `daemon.py`, líneas 34–35

```python
for watcher in watchers:
    watcher.scan()  # ← sin try/except
```

Si `scan()` lanza `OSError` (disco lleno, GVFS error), el daemon completo muere. Debería loguear y continuar.

---

### [ROB-2] `ollama.py` — `stop()` usa `pkill` sin verificar si el proceso existe
**Archivo:** `ollama.py`, líneas 116–119

```python
subprocess.run(["pkill", "-f", "ollama serve"], capture_output=True, timeout=3)
```

Si Ollama no está corriendo, `pkill` retorna exit code 1 que se ignora (correcto). Pero en sistemas donde `pkill` no existe (algunos Docker minimalistas), esto lanza `FileNotFoundError` que cae en el `except Exception: pass`. Documentar que `pkill` es un requisito o usar `psutil.process_iter` directamente.

---

### [ROB-3] `prompts.py` — `MCP discovery` silencia todas las excepciones
**Archivo:** `prompts.py`, líneas 60–62

```python
except Exception:
    # MCP discovery must never prevent a normal conversational reply.
    pass
```

El comentario justifica silenciar la excepción para disponibilidad. Pero sin log, si el MCP manager tiene un bug persistente, nunca se detectará.

**Fix:** Agregar un `logger.debug()` mínimo.

---

### [ROB-4] `config.py` — directorio de DB creado con `except Exception: pass`
**Archivo:** `config.py`, línea ~44

Si el directorio no se puede crear (permisos, disco lleno), el error aparecerá más tarde como un críptico `sqlite3.OperationalError: unable to open database file`.

---

### [ROB-5] `cli.py` — `prompt` con texto que no matchea ninguna acción cae en `decide_and_run` sin validación de tipo
**Archivo:** `cli.py`, línea 223

```python
task = {"type": None, "prompt": text, "complexity": parsed.get("complexity", 5)}
res = agent.decide_and_run(task)
print(res)
```

`print(res)` imprime el dict completo con toda la metadata del modelo en stdout. En una CLI eso es feo — debería usar `text_from_result(res)`.

---

### [ROB-6] `i18n.py` — `tr()` retorna la clave misma si no hay traducción (silencioso)
**Archivo:** `i18n.py`, línea 33

```python
message = MESSAGES[normalize_language(language)].get(key, MESSAGES["es"].get(key, key))
```

Si `key` no existe en ningún idioma, retorna `key` directamente (ej: `"path_required"`). Para el usuario final esto se ve como texto técnico en inglés. No hay log de clave faltante.

---

### [ROB-7] `coordinator.py` — `analyze_photo` corre agentes paralelos pero ignora `agent_failures` en el output
**Archivo:** `coordinator.py`, líneas 70–71

```python
output = {
    "ok": not failures,
    ...
    "agent_failures": failures,
}
```

Si hay fallos, `ok=False`. Pero el caller en `agent.py` o la capability de fotografía puede ignorar `agent_failures` y usar los `results` parciales como si fueran completos (por ejemplo usar `technical = results.get("technical_photo", {})` que es `{"available": False, "error": "..."}`) → análisis incompleto presentado como completo.

---

## 7. Calidad de Código y DRY

### [DRY-1] `model_manager.__init__` y `reload()` — duplicación total
**Archivo:** `model_manager.py`

`reload()` copia los mismos 8+ bloques de asignación de `__init__`. Extraer `_apply_config(config)`.

---

### [DRY-2] `folder_resolver.py` — `_normalize` idéntica a `sqlite._normalize_folder_name`
**Archivo:** `folder_resolver.py:34`, `sqlite.py:809`

```python
# En FolderResolver:
value = unicodedata.normalize("NFKD", str(value).casefold())
value = "".join(char for char in value if not unicodedata.combining(char))
return re.sub(r"\s+", " ", re.sub(r"[^\w ]", " ", value)).strip()

# En Memory:
value = unicodedata.normalize("NFKD", str(value).casefold())
value = "".join(char for char in value if not unicodedata.combining(char))
return re.sub(r"\s+", " ", re.sub(r"[^\w ]", " ", value)).strip()
```

Código idéntico en dos módulos. Extraer a `ada.domain.text_utils.normalize_folder_name()`.

---

### [DRY-3] `web_chat.py` — lógica de detección de intención de filesystem duplicada con `router.py`
**Archivo:** `web_chat.py:377`, `router.py`

`web_chat._filesystem_intent()` implementa su propia detección por regex en paralelo al router. Si se cambia un patrón en uno, el otro queda desactualizado.

---

### [DRY-4] `cli.py` — heurísticas de path extraction duplicadas tres veces
**Archivo:** `cli.py`, líneas 140–162

```python
for p in parts:
    if p.startswith("/") or p.startswith("~") or p.startswith("."):
        path = os.path.expanduser(p)
        break
```

Esta lógica aparece 3 veces en el mismo archivo para `index`, `suggest` y `organize`. Extraer a `_extract_path_from_args(parts)`.

---

### [DRY-5] `web_chat.py` — `_remember(state, text, reply)` + `return` repetido ~15 veces
**Archivo:** `web_chat.py`

Casi cada branch del método `handle()` termina con:
```python
self._remember(state, text, reply)
return {"reply": reply, "model": "..."}, 200
```

Un `_return_reply(state, text, reply, model, ...)` que encapsula ambas operaciones limpiaría mucho el código.

---

### [DRY-6] `autonomy.py` — Geofence con Haversine inline vs ningún test
**Archivo:** `autonomy.py`, líneas 88–107

La implementación de Haversine es correcta y bien documentada. Pero no tiene ningún test unitario. Es la fórmula más susceptible a errores de signo o conversión de unidades.

---

### [QUALITY-1] `memory_refiner.py` — `match.group(1)` capturado pero descartado
**Archivo:** `memory_refiner.py`, línea ~174

Los patrones de detección usan grupos de captura (`r"\brecord[aá]\s+(que|que)\s+(.*)"`) para extraer la frase relevante, pero el código usa `clean_fact = text.strip()` (el texto completo). Si el texto tiene más de 300 caracteres, se descarta aunque la parte capturada sea corta.

---

### [QUALITY-2] `web_chat.py` — versión hardcodeada en `/version`
**Archivo:** `web_chat.py`, línea 306

```python
reply = "ADA versión 0.1.0"
```

Debería leer la versión de `importlib.metadata.version("ada-local")` o de una constante central.

---

### [QUALITY-3] `model_manager.py` — `selection_summary` construye string de descripción con concatenación manual
**Archivo:** `model_manager.py`, línea ~304

Construye strings descriptivos manualmente con condicionaes anidadas. Difícil de mantener. Un `dataclass` o template string sería más legible.

---

### [QUALITY-4] `cli.py` — `load_config()` local que duplica la del módulo `config`
**Archivo:** `cli.py`, líneas 27–34

```python
def load_config():
    ...
    try:
        return load_validated_config(cfg_path, PROJECT_ROOT)
    except (OSError, ValueError) as exc:
        ...
        return {"name": "ADA", ...}  # fallback hardcodeado
```

`load_validated_config` ya tiene su propio fallback. La capa extra en CLI agrega divergencia.

---

### [QUALITY-5] `resources.py` — `hardware_profile()` usa VRAM solo si torch está instalado, pero no documenta que sin torch `vram_gb=0.0` siempre
**Archivo:** `resources.py`, líneas 74–82

Si `torch` no está instalado, `vram_gb = 0.0` siempre, lo que puede hacer que `model_manager` filtre modelos que requieren GPU aunque exista una. Debería intentar `nvidia-smi` como fallback.

---

## 8. Arquitectura

### [ARCH-1] `MemoryRefiner` accede a internals de `Memory` — acoplamiento estructural
**Archivo:** `memory_refiner.py`

`MemoryRefiner` usa `self.memory.conn` y `self.memory._lock` directamente. Si `Memory` cambia backend, `MemoryRefiner` se rompe. Exponer `list_recent_sessions()`, `prune_by_kind_and_age()`, `prune_tasks(keep=N)` en la interfaz de `Memory`.

---

### [ARCH-2] `web_chat.py` — God Object de 592 líneas con 4 responsabilidades distintas
**Archivo:** `web_chat.py`

Responsabilidades mezcladas:
1. **Routing de intención** (`_filesystem_intent`, `_food_advice_intent`, `_filesystem_followup`)
2. **Resolución de paths** (`_resolve_path`, `_dynamic_path`)
3. **Manejo de confirmaciones pendientes** (`pending_action`, `pending_path_action`)
4. **Formateo de respuestas** (generación del `reply` en cada branch)

Propuesta de split:
- `IntentClassifier` → (1)
- `PathResolver` → (2) (ya existe `FolderResolver`, pero `web_chat` tiene lógica propia extra)
- `PendingActionHandler` → (3)
- `ResponseFormatter` → (4)

---

### [ARCH-3] `daemon.py` — no hay observabilidad del estado del daemon
**Archivo:** `daemon.py`

El daemon corre en un `while True` sin exponer su estado. Si el scheduler falla continuamente, no hay forma de saberlo sin revisar los logs. Debería escribir un archivo de health periódicamente (como ya hace el bot de Telegram con `telegram-health.json`).

---

### [ARCH-4] `capabilities/registry.py` — `_LOADED_SPECS` global mutable compartido
**Archivo:** `registry.py`

Ver BUG-I10. El estado global compartido es una fuente de bugs en entornos multi-threaded.

---

### [ARCH-5] `Scheduler` y `EventBus` acoplan directamente a `Memory`
**Archivo:** `scheduler.py`, `event_bus.py`

`EventBus.__init__(memory)` y `Scheduler.__init__(memory, ...)` toman directamente el objeto `Memory`. Esto acopla el bus de eventos a SQLite. Si se quisiera un backend de eventos diferente (Redis, etc.), habría que reescribir. Un protocolo/interfaz `EventStore` sería más limpio.

---

### [ARCH-6] `mypy` configurado para Python 3.12 pero el proyecto soporta `>=3.9`
**Archivo:** `pyproject.toml`, línea 58

```toml
[tool.mypy]
python_version = "3.12"
```

Puede ocultar incompatibilidades de tipo en 3.9–3.11. Cambiar a `"3.9"`.

---

### [ARCH-7] Idioma mezclado — sin convención clara
Variables en inglés, comentarios en inglés/español, mensajes de usuario en español, mensajes de log en inglés/español. Sin convención documentada.

---

## 9. Testing

### [TEST-1] Cobertura mínima — solo `test_memory_refiner.py` con 3 tests básicos

El proyecto tiene un solo archivo de tests con 3 casos de happy path. Falta cobertura de:

| Módulo | Tests faltantes críticos |
|--------|--------------------------|
| `model_manager` | `choose()` con `privacy=high`, fallback chain cuando todos los modelos fallan |
| `router` | Routing de alimentos, verificación de mutación, JSON malformado del modelo |
| `policy` | `path_prefix` bypass (SEC-4), `validate_command` con comandos en whitelist |
| `autonomy` | `_inside_geofence` con coordenadas limítrofes, acción faltante |
| `folder_resolver` | Timeout de GVFS, path fuera de base, alias obsoleto |
| `sqlite` | Migración con `user_version` inconsistente, FTS vs. non-FTS |
| `web_chat` | Pending action flow, greeting, versión |
| `memory_refiner` | Hecho duplicado no se duplica, ciclo sin memoria, intervalo mínimo |

---

### [TEST-2] `test_memory_refiner.py` — `test_prune_old_tasks` no verifica comportamiento
**Archivo:** `tests/test_memory_refiner.py`, línea 46

```python
self.assertIsInstance(pruned, int)  # ← solo verifica que retorna un int
```

No verifica que efectivamente se purguen tareas cuando hay más de `keep=500` — el test siempre pasa aunque `_prune_old_tasks` retorne 0.

---

### [TEST-3] No hay tests de integración para el flujo completo `web_chat → agent → skill`
El flujo más crítico del sistema (usuario envía mensaje → `web_chat.handle()` → `agent.decide_and_run()` → skill) no tiene ningún test de integración.

---

### [TEST-4] No hay tests para `FolderResolver` ni `TriggerManager`
Ambas son clases complejas con lógica de estado y efectos secundarios (filesystem, subprocesos). Sin tests, cualquier refactor es riesgoso.

---

## ✅ Checklist de Acción

### 🔴 Críticos (bugs que afectan comportamiento o estabilidad)

- [x] **[BUG-C1]** Corregir orden de prioridad en `choose()` de `model_manager` — `privacy=high` y complejidad local evaluadas antes del fallback genérico
- [x] **[BUG-C2]** Refactorizar `refine_cycle` en `MemoryRefiner` para eliminar riesgo de deadlock
- [x] **[BUG-C3]** Agregar manejo de `SIGTERM`/`SIGINT` en `daemon.py` para shutdown limpio
- [x] **[BUG-C4]** Limitar `FolderWatcher._seen` para evitar memory leak en directorios grandes
- [x] **[THREAD-4]** Verificar y corregir posible deadlock en `LocalModelRuntime.ensure_ready()` → `start()` usando `RLock`
- [x] **[BUG-I1]** Corregir scope de `mem` en `cli.py` para el comando `backup`

### 🟠 Seguridad

- [x] **[SEC-1]** Mover API key de Gemini de query param a header `x-goog-api-key`
- [x] **[SEC-2]** Agregar whitelist explícita para `table`/`column` en `_migrate_sensitive_rows`
- [x] **[SEC-3]** Proteger `_log_tail` con try/except alrededor de `_resolve_token`
- [x] **[SEC-4]** Corregir comparación `path_prefix` en `autonomy._matches` — usar `Path.resolve().relative_to()`
- [x] **[SEC-6]** Agregar manejo de `HTTPError` en `_call_groq` y `_call_gemini`

### 🟡 Concurrencia

- [x] **[THREAD-1]** Agregar lock en `_call_gpt4all` para la inicialización lazy de `self._gpt4all`
- [x] **[THREAD-2]** Revisar ventana de condición de carrera en watchdog de Telegram vs. `stop()`
- [x] **[PERF-1]** Mover `FolderWatcher.rglob()` a un escaneo acotado con manejo de errores de permisos y montajes
- [x] **[BUG-I10]** Sincronizar acceso a `_LOADED_SPECS` global en `capabilities/registry.py`

### 🟢 Bugs menores / robustez

- [x] **[BUG-I2]** Reemplazar subproceso `test -d` por `Path.is_dir()` con thread timeout y fallback seguro en `folder_resolver`
- [x] **[BUG-I3]** Inicializar `saved = {}` antes del bloque de lectura en `_persist_enabled`
- [x] **[BUG-I4]** Eliminar variable `low` sin usar en `memory_refiner`
- [x] **[BUG-I5]** Usar `time.time_ns()` en nombres de hechos aprendidos
- [x] **[BUG-I6]** Leer versión de `importlib.metadata` en lugar de string hardcodeado
- [x] **[BUG-I7]** Agregar búsqueda acotada antes del fallback Python en `knowledge()`/`search_text()`
- [x] **[BUG-I8]** Agregar commit explícito entre pasos de migración en `_apply_migrations`
- [x] **[BUG-I9]** Extraer `_apply_config()` en `ModelManager` para eliminar duplicación `__init__`/`reload()`
- [x] **[ROB-1]** Envolver `watcher.scan()` en try/except en `daemon.py`
- [x] **[ROB-3]** Agregar `logger.debug()` en el silencio del MCP discovery en `prompts.py`
- [x] **[ROB-4]** Logear advertencia en `config.py` cuando no se puede crear el directorio de la DB
- [x] **[ROB-5]** Reemplazar `print(res)` por `print(text_from_result(res))` en `cli.py`
- [x] **[ROB-7]** Verificar que los callers de `coordinator.analyze_photo` manejen `agent_failures`

### 🔵 Calidad y DRY

- [x] **[DRY-1]** Extraer `_apply_config(config)` en `ModelManager`
- [x] **[DRY-2]** Unificar y normalizar manejo de carpetas y textos
- [x] **[DRY-4]** Extraer `_extract_path_from_args(parts)` en `cli.py`
- [x] **[DRY-6]** Agregar tests unitarios para la fórmula Haversine en `autonomy.py`
- [x] **[QUALITY-1]** Usar `match.group(1)` y extracción limpia en `_detect_user_fact_or_preference`
- [x] **[QUALITY-5]** Agregar fallback a `nvidia-smi` en `hardware_profile()` cuando torch no está disponible
- [x] **[PERF-2]** Cachear procedimientos frecuentes en RAM en `PromptBuilder`
- [x] **[PERF-3]** Cachear `capability_catalog()` con timestamp en lugar de recargar módulos en cada llamada
- [x] **[PERF-4]** Reemplazar lista con `del values[:-1000]` por `deque(maxlen=1000)` en `Metrics`
- [x] **[PERF-5]** Pasar `limit` real a `Memory.conversation()` en lugar de cargar 1000 mensajes siempre

### 🔮 Arquitectura / Deuda técnica

- [x] **[ARCH-1]** Agregar métodos `list_recent_sessions()` y `prune_by_kind_and_age()` a `Memory`
- [x] **[ARCH-2]** Refactor modular en curso documentado para separación de responsabilidades en chat
- [x] **[ARCH-3]** Agregar health file periódico al daemon (`daemon-health.json`)
- [x] **[ARCH-5]** Definir protocolo `EventStore` para desacoplar `EventBus`/`Scheduler` de SQLite
- [x] **[ARCH-6]** Cambiar `mypy.python_version` de `"3.12"` a `"3.9"`
- [x] **[ARCH-7]** Documentar convención de idioma

### 🧪 Testing

- [x] **[TEST-1]** Agregar tests unitarios para `choose()`, fallback chain, `autonomy._matches`, geofence, `sqlite`, `web_chat`
- [x] **[TEST-2]** Corregir `test_prune_old_tasks` para verificar el comportamiento real (>500 tareas purgadas)
- [x] **[TEST-3]** Agregar tests de integración para el flujo web chat y agents
- [x] **[TEST-4]** Agregar tests para `FolderResolver` y `PolicyEngine`

