# 12. Registro único de tools y routing estructurado

## Objetivo

Reemplazar el muro de regex en español para detectar intenciones por un registro único de herramientas que alimente comandos directos, routing, validación y ejecución. La capacidad nueva debe agregarse una sola vez y quedar disponible para las cuatro capas del flujo.

## Estado de implementación

| ID | Mejora / Corrección | Estado |
|---|---|---|
| ARQ-04 | Registro único con nombre, descripción, JSON Schema, handler y confirmación | ✅ Implementado |
| ARQ-05 | Dispatcher exacto para comandos `/v`, `/i`, `/r`, etc. | ✅ Implementado |
| ARQ-06 | Router pequeño, determinista y sin contexto completo | ✅ Implementado |
| ARQ-07 | Validación de tool y parámetros antes de ejecutar; fallback a chat | ✅ Implementado |
| ARQ-08 | Suite de evaluación para comandos, chat, MCPs y seguridad | ✅ Implementado |
| ARQ-09 | Selector de modelos LiteLLM informado por señales del router | ✅ Implementado |

## Flujo de cuatro capas

```text
mensaje
  │
  ├─ ¿empieza con "/"? ─ SÍ ─► Capa 1: dispatcher exacto, sin modelo
  │                                  └─ /v /i /r ...
  └─ NO
      │
      ├─ Capa 2: router (1 llamada, 0 contexto, salida JSON)
      │            └─ {tool, parameters, confidence}
      │
      ├─ tool válida ───────────────► Capa 3: validar + confirmar + ejecutar
      │
      └─ tool nula/dudosa/fallida ──► Capa 4: fallback chat con contexto
```

La primera capa resuelve shortcuts instantáneos. La segunda reemplaza las regex para lenguaje natural. La tercera es una barrera de seguridad independiente. La cuarta conserva el comportamiento conversacional para preguntas, explicaciones y solicitudes ambiguas.

## ARQ-04: fuente de verdad única

Todo debe generarse desde el registro: comandos, catálogo del router, schemas de parámetros, handlers y confirmaciones. Nunca deben mantenerse listas duplicadas por idioma o por interfaz.

```python
from dataclasses import dataclass
from typing import Callable, Optional

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict                 # JSON Schema
    handler: Callable[..., dict]
    command: Optional[str] = None
    requires_confirmation: bool = False

REGISTRY: dict[str, Tool] = {}

def register(tool: Tool):
    REGISTRY[tool.name] = tool

register(Tool(
    name="deployed_version",
    command="/v",
    description="Muestra la versión deployada de la aplicación.",
    parameters={"type": "object", "properties": {}, "required": []},
    handler=lambda: {"reply": f"Versión {get_version()}"},
))
register(Tool(
    name="team_info",
    command="/i",
    description="Muestra información del equipo, recursos y estado.",
    parameters={"type": "object", "properties": {}, "required": []},
    handler=lambda: {"reply": team_info_text()},
))
register(Tool(
    name="restart",
    command="/r",
    requires_confirmation=True,
    description="Reinicia el servicio.",
    parameters={"type": "object", "properties": {}, "required": []},
    handler=lambda: {"reply": do_restart()},
))
```

Una tool de filesystem puede declarar `path` como parámetro requerido y dejar que el mismo schema se use para prompt, validación y documentación.

## ARQ-05: dispatcher de comandos

Los comandos conocidos no necesitan un modelo ni regex:

```python
COMMANDS = {t.command: t for t in REGISTRY.values() if t.command}

def try_command(text: str):
    parts = text.strip().split(maxsplit=1)
    tool = COMMANDS.get(parts[0].lower())
    if not tool:
        return None
    if tool.requires_confirmation:
        return {"pending": tool.name, "reply": f"¿Confirmás {tool.name}? (sí/no)"}
    return tool.handler()
```

## ARQ-06: router JSON con contexto mínimo

Para los mensajes que no son comandos, el router usa un modelo pequeño/local y recibe solamente el catálogo y la consulta actual. No arrastra el historial completo.

```python
def build_router_prompt():
    lines = []
    for tool in REGISTRY.values():
        props = tool.parameters.get("properties", {})
        params = ", ".join(f"{k}: {v.get('type')}" for k, v in props.items())
        lines.append(
            f"- {tool.name}: {tool.description} | "
            f"params: {params or 'sin parámetros'}"
        )
    return (
        "Sos un router. Elegí la tool que resuelve el mensaje y extraé sus "
        "parámetros. Si ninguna aplica, devolvé tool=null.\n\n"
        "TOOLS DISPONIBLES:\n" + "\n".join(lines) + "\n\n"
        'Respondé SOLO JSON: {"tool": <nombre|null>, '
        '"parameters": {...}, "confidence": 0..1}'
    )
```

La llamada debe ser determinista (`temperature=0`) y usar structured output/JSON Schema cuando el proveedor lo soporte:

```json
{
  "type": "object",
  "properties": {
    "tool": {"type": ["string", "null"]},
    "parameters": {"type": "object"},
    "confidence": {"type": "number"}
  },
  "required": ["tool", "parameters", "confidence"],
  "additionalProperties": false
}
```

El umbral de confianza inicial sugerido es `0.5`; debe medirse con la suite de evaluación y ajustarse según falsos positivos y falsos negativos.

## ARQ-07: ejecución, validación y fallback

El router propone, pero nunca ejecuta directamente. Antes de llamar al handler, el código debe:

1. comprobar que la tool existe en el registro;
2. rechazar propuestas por debajo del umbral;
3. validar parámetros contra el JSON Schema;
4. verificar autorización de la capacidad;
5. exigir confirmación si `requires_confirmation` es verdadero;
6. ejecutar el handler registrado;
7. caer al chat si la propuesta es nula, dudosa o inválida.

```python
def execute(routed: dict, confirmed=False):
    name = routed.get("tool")
    if not name or name not in REGISTRY:
        return None
    if routed.get("confidence", 0) < 0.5:
        return None
    tool = REGISTRY[name]
    if tool.requires_confirmation and not confirmed:
        return {"pending": name, "reply": f"¿Confirmás {name}?"}
    validate_json_schema(tool.parameters, routed.get("parameters", {}))
    return tool.handler(**(routed.get("parameters", {}) or {}))
```

El orquestador completo queda conceptualmente así:

```python
def handle(text, history):
    if text.lstrip().startswith("/"):
        command = try_command(text)
        if command is not None:
            return command
    routed = route(text)
    result = execute(routed)
    if result is not None:
        return result
    return fallback_chat(text, history)
```

## Trade-offs

- El router añade una llamada, aunque sea chica; se puede cachear la clasificación de mensajes idénticos.
- El contexto cero no resuelve referencias como “y ahí adentro”; para esos casos puede pasarse una o dos líneas recientes, sin enviar todo el historial.
- Los parámetros mal extraídos deben producir fallback, nunca una ejecución parcial o silenciosa.
- Los comandos directos siguen siendo rápidos y no dependen de disponibilidad del modelo.
- La solución es multilingüe en la capa de lenguaje natural sin mantener patrones por idioma.

## ARQ-08: suite de evaluación

La migración debe medirse con casos de identidad, comandos, chat, follow-up, comida, filesystem, razonamiento, diagnósticos, métricas, seguridad y MCPs oficiales. Cada caso debe declarar categoría, timeout y una condición verificable (`must_contain` o `must_match`).

Como mínimo, la suite debe cubrir:

| Grupo | Casos representativos |
|---|---|
| Comandos | `/v`, `/i`, repetición de comandos, consulta de versión en lenguaje natural |
| Chat | explicación científica, saludo, follow-up con contexto, solicitud ambigua |
| Tools | comida, fotos, filesystem readonly, Drive, Calendar y Gmail |
| Seguridad | explicación de permisos sin acceder/modificar archivos |
| Diagnóstico | Telegram, métricas stale, timeouts y modos de modelo |

Cada caso debe comprobar que el routing elige la capacidad correcta, que las acciones sensibles piden confirmación y que las consultas sin tool caen al modelo conversacional.

## ARQ-09: selector de modelos para LiteLLM

### Objetivo

La llamada a LiteLLM no debe tener un modelo fijo e indiferenciado. ADA debe contar con un selector que elija el modelo o la cadena de fallback adecuada según la naturaleza de la tarea, su complejidad, los requisitos de privacidad, la latencia esperada y las capacidades necesarias.

El router no ejecuta la selección final ni debe conocer secretos de proveedores. Su responsabilidad es devolver señales estructuradas y explicables; el selector transforma esas señales en un modelo concreto y LiteLLM realiza la llamada.

```text
mensaje
   ↓
router estructurado
   ↓
{ tool, parameters, task_type, complexity, model_hint, ... }
   ↓
ModelSelector
   ├─ política de modelos
   ├─ disponibilidad/capacidades
   ├─ privacidad y presupuesto
   ├─ latencia/coste
   └─ fallbacks
   ↓
LiteLLM: completion(model=..., fallbacks=[...])
```

### Señales que debe emitir el router

El JSON del router debe conservar `tool`, `parameters` y `confidence`, y sumar información suficiente para que el selector tenga una base objetiva:

```json
{
  "tool": null,
  "parameters": {},
  "confidence": 0.94,
  "task_type": "reasoning",
  "complexity": 7,
  "model_hint": "reasoning",
  "required_capabilities": ["long_context"],
  "privacy": "normal",
  "latency": "balanced",
  "requires_tool_calling": false,
  "estimated_output_tokens": 900
}
```

Campos y semántica:

| Campo | Valores / ejemplo | Uso del selector |
|---|---|---|
| `task_type` | `chat`, `reasoning`, `coding`, `vision`, `tools`, `classification` | Mapea a un rol/política de modelos |
| `complexity` | Entero `1..10` | Elige modelo liviano, medio o potente |
| `model_hint` | `chat`, `fast`, `reasoning`, nombre lógico | Preferencia, nunca autorización absoluta |
| `required_capabilities` | `long_context`, `vision`, `json_schema`, `tool_calling` | Filtra modelos incompatibles |
| `privacy` | `high`, `normal`, `low` | Restringe proveedores remotos cuando corresponde |
| `latency` | `fast`, `balanced`, `quality` | Prioriza velocidad o calidad |
| `requires_tool_calling` | `true/false` | Exige soporte de tools/structured output |
| `estimated_output_tokens` | Entero positivo | Comprueba presupuesto de contexto y tokens |

Los campos deben tener enums, rangos y defaults definidos en el schema. Si el modelo router devuelve un valor inválido, el selector debe normalizarlo o usar defaults conservadores; nunca debe fallar hacia un modelo remoto de mayor privilegio.

### Contrato del selector

```python
selection = selector.choose(
    task_type="reasoning",
    complexity=7,
    model_hint="reasoning",
    required_capabilities=["long_context"],
    privacy="normal",
    latency="balanced",
    requires_tool_calling=False,
    estimated_output_tokens=900,
)

# Resultado explicable y auditable
{
    "model": "ollama/qwen3:8b",
    "fallbacks": ["openai/gpt-4o-mini"],
    "provider": "ollama",
    "role": "reasoning",
    "reason": "complexity=7; requiere long_context; privacidad normal",
}
```

El selector debe considerar, en este orden:

1. restricciones duras: privacidad, capacidad requerida, modelo instalado y disponibilidad;
2. política explícita del usuario o del sistema;
3. `task_type` y `model_hint` del router;
4. complejidad, tokens estimados y presupuesto de contexto;
5. latencia/coste y métricas históricas;
6. fallbacks compatibles.

`model_hint` es una pista, no una orden. El selector puede ignorarla si el modelo no está disponible, no soporta la capacidad requerida o contradice una política de privacidad.

### Integración con LiteLLM

LiteLLM debe recibir el modelo ya resuelto, no decidir de forma opaca a partir de texto libre:

```python
selection = model_selector.choose(router_result, runtime_context)
response = litellm.completion(
    model=selection["model"],
    fallbacks=selection["fallbacks"],
    messages=messages,
    temperature=temperature_for(router_result),
    max_tokens=selection["max_tokens"],
    response_format=selection.get("response_format"),
)
```

La telemetría debe registrar `task_type`, `complexity`, `selected_model`, `provider`, `fallback_used`, latencia, tokens y motivo de selección, sin guardar prompts ni secretos innecesarios.

### Reglas de seguridad y degradación

- Nunca aceptar del router un nombre de modelo arbitrario para ejecutar directamente; `model_hint` debe resolverse contra un catálogo allowlisted.
- Si falta `task_type` o `complexity`, usar `chat` y complejidad media, no el modelo más potente.
- Si la salida requiere JSON, el selector debe filtrar modelos sin structured output y elegir un fallback compatible.
- Si `privacy=high`, excluir proveedores remotos aunque el router sugiera un modelo remoto.
- Si el router falla, usar la política de rol existente; no enviar el historial completo al router como mecanismo de recuperación.
- Si el modelo principal falla, el fallback debe respetar las mismas restricciones de capacidad y privacidad.

### Criterios de aceptación

- El router devuelve JSON válido con `task_type`, `complexity` y `model_hint` además de tool/parámetros.
- El selector nunca elige modelos fuera del catálogo permitido ni viola privacidad.
- Dos tareas con distinta complejidad pueden seleccionar modelos distintos de forma determinista.
- Un hint inválido, un modelo ausente o una capacidad incompatible producen fallback explicable.
- La llamada LiteLLM recibe el modelo resuelto, sus fallbacks y el formato de respuesta requerido.
- Las métricas permiten explicar por qué se eligió un modelo y medir si la decisión mejoró latencia/calidad.
