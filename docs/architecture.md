# Arquitectura

## Decisión base

ADA usa arquitectura hexagonal (ports and adapters) con organización por
contexto funcional. Hexagonal define la dirección de dependencias; los
paquetes por contexto evitan que el proyecto se convierta en un único paquete
`service` o `util`.

```text
infrastructure/in  ->  application  ->  domain
infrastructure/out ->  application  ->  domain
                    ^
                    |
          puertos definidos por application
```

Spring Boot queda en el borde: configuración, inyección, HTTP, persistencia,
clientes y métricas. El dominio debe poder probarse sin levantar Spring.

## Estructura inicial

```text
src/main/java/com/ada/
├── shared/
│   ├── domain/          tipos y errores transversales mínimos
│   └── application/     clock, ids, resultado y políticas comunes
├── conversation/
│   ├── domain/
│   ├── application/
│   │   ├── dto/         contratos internos de casos de uso
│   │   ├── port/in/     casos de uso públicos
│   │   └── port/out/    dependencias requeridas
│   └── infrastructure/
│       ├── in/rest/     controllers, dto/ y mapper/
│       └── out/         LiteLLM, SQLite, auditoría
├── memory/
├── capability/
├── model/
└── observability/
```

El contexto que se envía al modelo se compone en `conversation.context`. Cada
fragmento tiene un `ContextItem` independiente (`system`, `prompt`, `tools`,
`memories`, `tool_response`, `compacted_prompt` y `response`).
`ContextManager` recibe `List<ContextItem>` y respeta el orden declarado con
`@Order`. Cada item recibe el estado acumulado y devuelve el siguiente estado;
por eso `CompactedPromptContextItem` puede eliminar mensajes anteriores y
reemplazarlos por `compacted_prompt` antes de continuar.

La coordinación de capacidades vive en `conversation.manager`: `ContextManager`
ensambla el contexto, `ToolManager` reúne proveedores y ejecutores de tools, y
`MemoryManager` evalúa si una interacción contiene una instrucción explícita y
durable que justifique guardarla. Las memorias no se crean por una conversación
ordinaria; la política evita capturar información accidental y queda preparada
para reemplazar el almacenamiento en memoria por un puerto persistente.

Los nombres concretos pueden variar por contexto, pero no se mezclan entradas,
casos de uso, dominio y salidas en la misma clase.

## Separación de modelos

```text
infrastructure.in.rest.dto  -> JSON HTTP; no sale del adapter REST
infrastructure.in.rest.mapper -> mapeos HTTP <-> application
application.dto              -> entrada/salida de casos de uso
application.mapper           -> mapeos internos de application, si fueran necesarios
shared.infrastructure.dto    -> configuración transversal transportada como DTO
domain.entity                -> identidad, persistencia y ciclo de vida
domain.bo                    -> reglas de negocio e invariantes
infrastructure.out.*.dto     -> formato específico de un proveedor externo
infrastructure.out.*.mapper  -> mapeos application <-> proveedor externo
```

Un controller transforma explícitamente su DTO REST a un DTO de application.
Un adapter externo transforma entre el contrato de application y su DTO de
infraestructura. Entidades y BO nunca se exponen directamente por HTTP.

`SqliteSystemPromptProvider` es un adapter de salida: implementa un puerto de
application y lee la versión activa desde `system_prompts` en SQLite. No hay un
prompt default hardcodeado en el código.

Las memorias se aíslan por `conversationId`, que forma parte del request de
application y se propaga desde el DTO REST. El manager nunca mezcla memorias de
dos conversaciones. El evaluador LLM devuelve un `subject` estable para
reemplazar una preferencia existente; si no lo devuelve, se usa el contenido
completo normalizado, nunca solo la primera palabra.

La capa RAG vive junto a tools y memories como un `ContextItem` independiente.
`RagManager` recupera documentos mediante el puerto `RagDocumentStore`; el
adaptador actual usa SQLite FTS5, filtra por `conversationId` y aplica límites
de cantidad y caracteres antes de agregar conocimiento al contexto.

Las invocaciones de los `ContextItem` se miden transversalmente con
`ContextMetricsAspect`: se registra un contador de invocaciones y un `Timer` de
duración por componente.

Cada ejecución genera un `messageId` y actualiza `MessageExecutionState` en
cada etapa del flujo. El estado se puede consultar en
`GET /api/v1/chat/{messageId}/status`; los estados con modelo o tool incluyen
el nombre en `detail`.
Los clientes interactivos pueden suscribirse a
`GET /api/v1/chat/{messageId}/events` mediante Server-Sent Events (SSE), que
envía el estado inicial y cada transición hasta `completed` o `failed`. El
endpoint REST permanece disponible como fallback.

El loop de tools agrega la respuesta del modelo como `response` y cada resultado
como `tool_response` antes de volver a invocar el modelo. Tiene un máximo de
ocho rondas para evitar loops infinitos.

## Strategy y Filter

Las variantes dinámicas se registran como componentes y se inyectan como
colecciones de interfaces:

```java
interface ModelSelectionStrategy {
    boolean supports(ChatRequest request);
    ModelSelection select(ChatRequest request);
}

interface RequestFilter {
    boolean supports(ChatRequest request);
    ChatRequest apply(ChatRequest request);
}

class SelectModelUseCase {
    SelectModelUseCase(List<ModelSelectionStrategy> strategies,
                       List<RequestFilter> filters) { }
}
```

Reglas:

- cada implementación declara explícitamente cuándo aplica;
- el orden se controla con `@Order` o una prioridad documentada;
- si ninguna estrategia aplica, el caso de uso falla con un error tipado;
- el agregador no conoce las clases concretas;
- no se resuelve comportamiento leyendo nombres de beans o con reflexión propia;
- filtros puros se ejecutan en una cadena determinista y observable.

## Flujo de una solicitud

1. Un adaptador de entrada valida formato y autenticación.
2. Un caso de uso crea el contexto de correlación y aplica filtros.
3. Una estrategia selecciona proveedor/modelo según política, capacidad,
   costo, latencia y disponibilidad.
4. Un puerto de salida invoca LiteLLM.
5. El caso de uso persiste resultado y auditoría mediante puertos.
6. Métricas, logs y errores se emiten sin filtrar secretos.

Las acciones potencialmente destructivas o externas requieren confirmación
explícita y deben poder producir un manifiesto de reversión cuando sea viable.
## Selección de contexto y modelos

ADA usa dos roles de modelo configurables:

- `ada.llm.routing-model` (`llama3.2:1b` por defecto) recibe un catálogo liviano y devuelve JSON con los MCPs, tools y memorias relevantes, además de indicar si debe compactarse el contexto.
- `ada.llm.default-model` (`qwen2.5:7b` por defecto) recibe únicamente el contexto y las tools seleccionadas y genera la respuesta o ejecuta el loop de tools.

La aplicación valida los nombres seleccionados contra los proveedores registrados. La selección no ejecuta herramientas y los tool-calls solo se aceptan cuando llegan en el campo estructurado del proveedor; nunca se interpreta texto arbitrario como una invocación.

El almacenamiento de modelos de Ollama se configura con `OLLAMA_DATA_DIR` en el entorno local y se monta como volumen. La ruta no se versiona.
