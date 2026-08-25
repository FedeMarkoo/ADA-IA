# Shared Context & Dynamic Memory for Multi-Model Ollama

## Objetivo

Reducir el consumo de memoria provocado por el contexto cuando ADA utiliza varios modelos Ollama en paralelo, evitando duplicar el historial completo en cada modelo.

La propuesta **no intenta compartir la KV cache entre modelos**. Ollama/modelos diferentes no pueden reutilizar directamente una misma KV cache. En cambio, ADA debe compartir una **fuente de verdad de contexto fuera del modelo** y construir un contexto pequeño y específico para cada request.

## Hallazgos en ADA actual

### 1. El router ya recibe historial, pero lo limita manualmente

`IntentRouter._prompt()` envía solamente los últimos 2500 caracteres de `history`, mientras que `_route_food()` usa 1200 caracteres. Esto demuestra que ya existe una política de contexto parcial, pero está implementada como truncado por caracteres y no como una estrategia centralizada de memoria.

### 2. La sesión mantiene hasta 1000 mensajes en memoria de proceso

`ChatService._remember()` conserva hasta 1000 mensajes por sesión. Esto no equivale directamente a KV cache de Ollama, pero puede hacer crecer el uso de RAM del proceso y obliga a cada capa que necesite contexto a decidir por su cuenta cuánto historial enviar.

### 3. ADA ya tiene una abstracción de memoria persistente

`MemoryLayers` expone capas `short_term`, `episodic`, `semantic` y `profile`, además de búsqueda semántica. Esto es una base adecuada para convertir el contexto compartido en una capacidad transversal en lugar de mantenerlo solamente en `SessionState`.

### 4. El ModelManager ya centraliza las llamadas a Ollama

`ModelManager._call_ollama()` construye el payload de `/api/chat` y permite configurar `num_ctx`, `num_predict`, `keep_alive` y otros parámetros. Por lo tanto, el control de presupuesto de contexto debe incorporarse en esta capa o inmediatamente antes de ella, no repartirse entre routers y servicios.

### 5. El runtime ya conoce los modelos instalados y la política de selección

`ModelManager` mantiene roles como `chat`, `router`, `reasoning`, `coding` y `tools`, y calcula políticas según hardware. Esto permite agregar un presupuesto de contexto por request y por rol sin romper la selección existente.

## Arquitectura propuesta

```text
                         ┌──────────────────────┐
                         │      ChatService      │
                         │ session_id + request  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Context Manager     │
                         │                      │
                         │  1. recent messages │
                         │  2. summary          │
                         │  3. semantic memory  │
                         │  4. profile          │
                         │  5. task context     │
                         └──────────┬───────────┘
                                    │
                         bounded context packet
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       Router         │
                         │ choose model/role    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     ModelManager     │
                         │ context budget       │
                         │ num_ctx / predict    │
                         └──────────┬───────────┘
                                    │
                     ┌──────────────┼──────────────┐
                     ▼              ▼              ▼
                  Ollama A       Ollama B       Ollama C
                     │              │              │
                     └──────────────┼──────────────┘
                                    │
                           respuestas / eventos
                                    │
                                    ▼
                         Shared Memory Store
```

## Qué significa “contexto compartido”

El contexto compartido debe ser **datos compartidos**, no una cache de inferencia compartida.

Ejemplo:

```text
Conversation 123

Summary:
  El usuario está trabajando en ADA-IA...

Recent:
  últimos 6-12 mensajes

Semantic memories:
  3 recuerdos relevantes para esta consulta

Profile:
  preferencias permanentes relevantes

Task state:
  modelo anterior = coding
  archivo actual = router.py
```

Cuando el router decide usar un modelo diferente, el modelo recibe solamente el `context packet` necesario para esa consulta.

## Context Packet

Agregar una estructura conceptual similar a:

```python
ContextPacket(
    conversation_id="main",
    summary="...",
    recent_messages=[...],
    memories=[...],
    profile=[...],
    task_state={...},
    token_budget=8192,
)
```

El packet debe ser independiente del modelo. No debe almacenar prompts específicos de Ollama ni depender del tokenizer de un modelo concreto.

## Presupuesto dinámico

No conviene asignar 4 GB de contexto a cada modelo de forma fija.

El presupuesto debería depender de:

- modelo seleccionado
- rol (`router`, `chat`, `reasoning`, `coding`, etc.)
- complejidad
- longitud de la consulta
- memoria disponible
- cantidad de modelos actualmente activos
- límite configurado por el usuario

Ejemplo conceptual:

```text
RAM/VRAM disponible para inferencia: 12 GB

router      -> 2K-4K tokens
chat        -> 8K tokens
coding      -> 16K tokens
reasoning   -> 24K tokens

pero el presupuesto se aplica solamente al modelo que procesa
la request actual.
```

Esto es preferible a mantener un contexto máximo grande en los tres modelos simultáneamente.

## Estrategia de memoria

### Nivel 1 — Recent context

Enviar únicamente los últimos mensajes necesarios para mantener continuidad inmediata.

Recomendación inicial: 6-12 mensajes, con límite por tokens y no por caracteres.

### Nivel 2 — Conversation summary

Cuando la conversación supera el presupuesto, generar/actualizar un resumen incremental.

El resumen debe reemplazar bloques antiguos del historial, no agregarse indefinidamente.

### Nivel 3 — Semantic memory

Usar `MemoryLayers.recall()` para recuperar recuerdos relacionados con la consulta.

No enviar toda la memoria semántica: solamente los resultados top-K que superen un umbral de relevancia.

### Nivel 4 — Profile

Recuperar únicamente preferencias o hechos persistentes relevantes.

### Nivel 5 — Task state

Mantener estado estructurado de la tarea actual fuera del LLM:

```json
{
  "current_file": "ada/application/router.py",
  "current_task": "optimizar contexto",
  "selected_role": "coding",
  "last_model": "..."
}
```

Esto evita gastar tokens explicando al modelo información que puede representarse como estado estructurado.

## Cambio importante: tokens, no caracteres

Actualmente el router utiliza cortes como `history[-2500:]` y `history[-1200:]`.

Eso debería reemplazarse por un `ContextBudget` basado en tokens.

Ejemplo:

```python
ContextBudget(
    total_tokens=8192,
    system_tokens=1200,
    recent_tokens=3000,
    memory_tokens=2000,
    task_tokens=1000,
    reserve_tokens=992,
)
```

El presupuesto debe reservar espacio para la respuesta cuando corresponda.

## Modelo activo vs. modelos residentes

El objetivo no debería ser necesariamente mantener los tres modelos con una KV cache grande.

Hay dos estrategias posibles:

### A. Residentes, contexto pequeño

Mantener los modelos cargados con `keep_alive`, pero usar un `num_ctx` moderado y un contexto externo compacto.

Ventaja: cambio de modelo rápido.

Desventaja: los pesos siguen ocupando memoria aunque el modelo no esté procesando.

### B. Pool dinámico

Permitir que ADA decida qué modelos deben permanecer residentes y cuáles pueden descargarse según presión de memoria.

Ventaja: menor consumo máximo.

Desventaja: cold starts al cambiar de modelo.

**Recomendación:** implementar primero A. Luego agregar B como optimización opcional.

## No intentar compartir KV cache entre modelos

Una implementación como:

```text
Modelo A ─┐
Modelo B ─┼──> misma KV cache
Modelo C ─┘
```

no debería formar parte de esta mejora.

La KV cache depende de los pesos, arquitectura, tokenizer y estado interno del modelo. Para modelos diferentes no es una memoria intercambiable.

La arquitectura correcta es:

```text
                 Shared Context Store
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
          Model A      Model B      Model C
          own KV       own KV       own KV
```

pero cada modelo recibe solamente el contexto que necesita.

## Cambios propuestos

### 1. Nuevo servicio `ContextManager`

Crear:

```text
ada/application/context_manager.py
```

Responsabilidades:

- construir `ContextPacket`
- calcular presupuesto de tokens
- seleccionar mensajes recientes
- recuperar memoria semántica
- recuperar profile relevante
- mantener/actualizar resumen
- evitar duplicados entre summary, recent y memories

### 2. Integrarlo con `ChatService`

`SessionState` debería conservar solamente estado operativo de sesión y una referencia a `session_id`.

El historial completo no debería ser la fuente primaria que se concatena en cada prompt.

### 3. Integrarlo con `MemoryLayers`

Agregar operaciones específicas para conversación:

```python
remember_message(...)
get_summary(...)
update_summary(...)
recall_context(...)
```

La persistencia puede continuar usando el store existente.

### 4. Integrarlo con `IntentRouter`

Cambiar:

```python
route(text, history="")
```

por algo conceptualmente equivalente a:

```python
route(text, context=ContextPacket(...))
```

El router debería recibir solamente el contexto necesario para resolver la intención.

Para la mayoría de consultas simples, incluso debería poder recibir **cero historial**.

### 5. Integrarlo con `ModelManager`

Agregar una política central:

```python
context_policy = {
    "router": {"num_ctx": 4096},
    "chat": {"num_ctx": 8192},
    "coding": {"num_ctx": 16384},
    "reasoning": {"num_ctx": 24576},
}
```

Y permitir overrides por request.

### 6. Presupuesto según presión de memoria

Agregar un `MemoryBudgetManager` o integrarlo al runtime de recursos.

Conceptualmente:

```text
available_memory
       │
       ▼
model_weight_budget
       │
       ├── active model
       └── context budget
```

No asumir que todo el presupuesto disponible puede convertirse en `num_ctx`.

Los pesos del modelo, KV cache, runtime y otros procesos necesitan margen.

## Optimización adicional: evitar llamadas innecesarias del router

El router actual ya tiene un fast-path para algunas consultas conversacionales simples: si no hay keywords de capability ni referencia contextual, devuelve `ask` sin llamar al modelo.

La nueva arquitectura debería ampliar esta idea:

```text
simple request
    │
    ├── deterministic route ──> model
    │
    └── no context required

contextual request
    │
    └── ContextManager ──> bounded packet ──> router/model
```

Esto reduce tanto tokens como KV cache.

## Ejemplo de flujo

Usuario:

> “¿Y qué modelo conviene para hacerlo?”

ADA no debería enviar 1000 mensajes anteriores a los tres modelos.

Debería resolver:

```text
recent context:
  últimos mensajes relevantes

summary:
  Estamos optimizando el router de ADA para Ollama.

task state:
  current task = context optimization

semantic memory:
  modelo X tiene mejor rendimiento para coding
```

Y producir aproximadamente:

```text
ContextPacket ≈ 3K-8K tokens
```

en lugar del historial completo.

## Resultado esperado

La mejora busca pasar de:

```text
3 modelos
×
contexto grande por modelo
×
KV cache independiente
```

a:

```text
1 memoria compartida y persistente
        │
        ├── contexto pequeño → modelo A
        ├── contexto pequeño → modelo B
        └── contexto pequeño → modelo C
```

No elimina la memoria necesaria para los pesos de los modelos, pero evita duplicar innecesariamente el historial y reduce la KV cache requerida por request.

## Métricas que deberían agregarse

Antes y después de implementar la mejora, registrar:

- `context.input_tokens`
- `context.summary_tokens`
- `context.memory_tokens`
- `context.recent_tokens`
- `context.total_tokens`
- `context.truncated`
- `context.retrieved_memories`
- `model.context_budget`
- `model.load_duration`
- `model.resident_duration`
- memoria utilizada antes/después de request
- tiempo de respuesta
- tokens/segundo

Esto permitirá comprobar si la optimización realmente reduce memoria sin degradar calidad.

## Fases recomendadas

### Fase 1 — Context Manager

- crear `ContextPacket`
- crear presupuesto por tokens
- centralizar recent/summary/memory/profile
- reemplazar truncados por caracteres

### Fase 2 — Integración

- ChatService
- Router
- Agent/application services
- ModelManager

### Fase 3 — Summary incremental

- resumen automático cuando se supera el presupuesto
- compaction de conversaciones antiguas
- persistencia del summary

### Fase 4 — Dynamic model residency

- detectar presión de memoria
- mantener modelos calientes según frecuencia
- reducir `keep_alive` cuando haya presión
- descargar modelos inactivos cuando sea necesario

### Fase 5 — Adaptive context

Aprender de las métricas qué tamaño de contexto necesita cada role/modelo.

## Criterio de aceptación

La implementación debería demostrar que:

1. El historial completo no se concatena automáticamente en cada request.
2. El contexto se construye una sola vez por request y se comparte entre las capas de ADA.
3. Cada modelo recibe un contexto acotado a su tarea.
4. `num_ctx` es configurable por role y request.
5. El sistema puede mantener varios modelos Ollama sin multiplicar innecesariamente el contexto histórico.
6. Las conversaciones largas siguen siendo coherentes gracias a summary + semantic retrieval.
7. Se puede medir el consumo de memoria y tokens antes/después.

## Conclusión

**Sí conviene implementar contexto compartido en ADA, pero como memoria/context packet externo, no como KV cache compartida.**

La base actual del proyecto es favorable: ya existen `MemoryLayers`, sesiones, router, selección por roles y un `ModelManager` centralizado para Ollama. La mejora debería unificar esas piezas en un `ContextManager` y convertir el tamaño del contexto en un recurso dinámico.

El beneficio principal será que los tres modelos puedan consultar la misma memoria lógica sin que ADA tenga que enviar el historial completo a cada uno. Esto permite aprovechar mejor la memoria disponible y, especialmente, escalar el sistema a más modelos sin multiplicar el costo del contexto de manera lineal.
