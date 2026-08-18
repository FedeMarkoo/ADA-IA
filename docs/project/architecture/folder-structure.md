# Estructura de carpetas por dominio y responsabilidades

## Corrección conceptual

La estructura no debe agrupar todo por tecnología ni por extensión de archivo.
Hay tres conceptos diferentes:

- **Dominio:** qué problema resuelve ADA (`photography`, `shopping`, `files`).
- **Aplicación:** qué caso de uso ejecuta (`analyze_photo`, `select_batch`,
  `generate_shopping_list`).
- **Infraestructura:** con qué tecnología lo hace (Ollama, SQLite, rawpy,
  Lightroom, Telegram).

Por eso:

- Ollama es un **engine/provider de modelos**, no un modelo de dominio ni el
  runtime general de ADA.
- `runtime` debe ocuparse únicamente del ciclo de vida de procesos, health
  checks, workers y recursos.
- Fotografía no debe esconderse dentro de `files`: el archivo RAW es una
  entrada, pero selección, contexto, ráfaga, revelado y Lightroom forman un
  dominio propio.
- `media` es demasiado genérico como carpeta principal. Las capacidades de
  imagen pertenecen a `photography`; los decodificadores concretos pertenecen a
  infraestructura.

## Estructura propuesta

```text
ADA/
├── README.md
├── pyproject.toml
├── config/
│   ├── default.json
│   └── local.example.json
├── src/
│   └── ada/
│       ├── bootstrap/
│       │   ├── application.py
│       │   ├── dependencies.py
│       │   └── settings.py
│       ├── domain/
│       │   ├── files/
│       │   │   ├── entities.py
│       │   │   ├── policies.py
│       │   │   └── services.py
│       │   ├── photography/
│       │   │   ├── entities.py
│       │   │   ├── analysis.py
│       │   │   ├── selection.py
│       │   │   ├── bursts.py
│       │   │   └── session.py
│       │   ├── shopping/
│       │   │   ├── entities.py
│       │   │   ├── lists.py
│       │   │   ├── inventory.py
│       │   │   └── recipes.py
│       │   ├── conversations/
│       │   └── automation/
│       │       ├── events.py
│       │       ├── tasks.py
│       │       └── rules.py
│       ├── application/
│       │   ├── commands/
│       │   ├── queries/
│       │   ├── workflows/
│       │   │   ├── analyze_photo.py
│       │   │   ├── select_photo_batch.py
│       │   │   ├── manage_shopping_list.py
│       │   │   └── respond_to_event.py
│       │   └── ports/
│       │       ├── llm.py
│       │       ├── vision.py
│       │       ├── persistence.py
│       │       └── notifications.py
│       ├── agents/
│       │   ├── registry.py
│       │   ├── coordinator.py
│       │   └── photography/
│       │       ├── technical.py
│       │       ├── context.py
│       │       └── reviewer.py
│       ├── capabilities/
│       │   ├── registry.py
│       │   ├── files/
│       │   ├── photography/
│       │   ├── shopping/
│       │   ├── data/
│       │   └── system/
│       ├── infrastructure/
│       │   ├── engines/
│       │   │   ├── ollama.py
│       │   │   ├── openai.py
│       │   │   └── anthropic.py
│       │   ├── imaging/
│       │   │   ├── rawpy_decoder.py
│       │   │   ├── pillow_decoder.py
│       │   │   └── exiftool.py
│       │   ├── persistence/
│       │   │   └── sqlite.py
│       │   ├── files/
│       │   │   └── local_filesystem.py
│       │   ├── integrations/
│       │   │   ├── lightroom.py
│       │   │   ├── telegram.py
│       │   │   └── mobile.py
│       │   └── runtime/
│       │       ├── process.py
│       │       ├── health.py
│       │       ├── scheduler.py
│       │       └── resources.py
│       └── interfaces/
│           ├── cli.py
│           ├── web/
│           │   └── server.py
│           └── messaging/
│               └── telegram.py
├── tests/
├── scripts/
└── docs/
```

## Por qué esta estructura tiene sentido

### `domain/`

Contiene conceptos y reglas que seguirían existiendo aunque cambiemos Python,
Ollama, SQLite o Telegram. Por ejemplo, una ráfaga, una selección fotográfica,
una lista de compras o una tarea autónoma pertenecen al dominio.

### `application/`

Contiene casos de uso. Orquesta dominio, agentes y puertos, pero no sabe si la
visión la hace Ollama, OpenAI o un modelo futuro. Aquí vive la diferencia entre
“analizar una foto” y “seleccionar un lote”.

### `agents/`

Contiene especialistas que producen evidencia o recomendaciones. Un agente no
debe escribir directamente en Lightroom ni abrir SQLite: usa puertos y casos de
uso.

### `capabilities/`

Es el reemplazo conceptual de `skills/`. Una capability es una herramienta que
ADA puede descubrir y ejecutar. Debe ser fina: valida argumentos, llama un caso
de uso y devuelve un resultado. Las reglas importantes no deben quedar
duplicadas dentro de cada frase del parser.

### `infrastructure/`

Contiene implementaciones intercambiables:

- `engines/ollama.py`: cliente del engine Ollama y sus opciones de inferencia;
- `imaging/`: rawpy, Pillow y ExifTool;
- `integrations/lightroom.py`: formato XMP y comunicación con Lightroom;
- `runtime/`: procesos, scheduler, health checks y límites de recursos;
- `persistence/`: SQLite y futuras bases;
- `files/`: filesystem local y permisos.

### `interfaces/`

Son las entradas y salidas de ADA. Web, CLI, Telegram y móvil convierten
mensajes externos en comandos o eventos. No deben contener reglas de fotos,
compras ni selección.

## Ubicación de los conceptos discutidos

| Concepto | Ubicación correcta | Motivo |
|---|---|---|
| Ollama | `infrastructure/engines/ollama.py` | proveedor de inferencia |
| modelo de visión | configuración + `application/ports/vision.py` | capacidad contratada, no dominio |
| proceso Ollama | `infrastructure/runtime/` | lifecycle y health del proceso |
| RAW/JPG | `domain/files` + `infrastructure/imaging` | archivo como entrada, decoder como tecnología |
| análisis fotográfico | `domain/photography` | regla y concepto del producto |
| agente fotógrafo | `agents/photography` | especialista que aporta evidencia |
| XMP/Lightroom | `infrastructure/integrations/lightroom.py` | formato e integración externa |
| ráfagas | `domain/photography/bursts.py` | regla de selección fotográfica |
| lista de compras | `domain/shopping` | producto y estado del usuario |
| Tasker/Telegram | `interfaces` o `infrastructure/integrations` | canales externos |
| CPU y workers | `infrastructure/runtime/resources.py` | operación del sistema |

## Mapeo de los archivos actuales

| Actual | Destino |
|---|---|
| `agent_loop.py` | `application` + `interfaces/cli.py` |
| `agent.py` | `application/workflows` legado |
| `memory.py` | `infrastructure/persistence/sqlite.py` |
| `models.py` | `infrastructure/engines/` |
| `runtime.py` | `infrastructure/runtime/` |
| `resource_policy.py` | `infrastructure/runtime/resources.py` |
| `image_embedding.py` | `infrastructure/imaging/embeddings.py` |
| `mcp_client.py` | `infrastructure/integrations/mcp.py` |
| `ui_server.py` | `interfaces/web/server.py` |
| `agents/` | `agents/` |
| `skills/photos/` | `capabilities/photography/` + `domain/photography/` |
| `skills/operations/files/` | `capabilities/files/` + `infrastructure/files/` |
| `skills/data/` | `capabilities/data/` |
| `skills/system/` | `capabilities/system/` |
| `ada.py` | `interfaces/cli.py` |

## Regla práctica

Antes de crear una carpeta nueva hay que responder dos preguntas:

1. ¿Esto es una regla/concepto del producto, un caso de uso o una tecnología?
2. ¿Quién debería poder cambiarlo sin modificar las otras dos capas?

Si la respuesta es una regla de fotografía, va a `domain/photography`. Si es
un decoder RAW concreto, va a `infrastructure/imaging`. Si es una orden que
coordina ambos, va a `application/workflows`. Si es un comando que el usuario
puede invocar, va a `capabilities/`.

## Migración segura

1. Crear el paquete nuevo y tests de arquitectura.
2. Mover primero runtime, engines y persistence, manteniendo módulos puente.
3. Separar dominio de fotografía de decodificadores y XMP.
4. Convertir `skills/` en capabilities delgadas.
5. Mover interfaces web y CLI al final.
6. Eliminar módulos puente solo cuando todos los imports y procedimientos estén
   actualizados.

No se debe hacer un `mv` masivo: la aplicación tiene imports absolutos,
cargador dinámico de skills y memoria persistente que pueden depender de las
rutas actuales.
