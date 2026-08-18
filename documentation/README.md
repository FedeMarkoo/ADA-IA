# ADA Documentation

ADA es un agente local orientado a automatizar tareas sobre archivos, fotos y
datos. Puede conversar, ejecutar skills, consultar memoria y pedir confirmación
antes de realizar operaciones que modifican información.

## Arquitectura autónoma de motores

ADA administra su motor local en lugar de exigir que el usuario inicie
Ollama manualmente. Al necesitar una respuesta generativa o visual, el
`ModelManager` consulta el runtime local, lo inicia si está instalado y
espera a que esté listo. Si el servicio ya estaba activo, ADA lo reutiliza y
no lo detiene al finalizar.

La capacidad se llama `local`; Ollama es su backend actual. La misma interfaz
permite sumar otros motores (`openai` y `anthropic`) mediante
`engine_priority`, sin acoplar los agentes a un proveedor específico.

En `config.json`:

- `local_runtime.auto_start`: arranque automático del runtime local.
- `local_runtime.auto_pull`: desactivado por defecto para evitar descargas
  inesperadas de modelos grandes.
- `engine_priority`: orden de fallback para tareas generativas complejas.
- `ollama_model` y `vision_model`: modelos de texto y visión.

El estado se puede consultar en `GET /api/status`. Incluye motores
disponibles, salud del runtime, modelos instalados y agentes registrados.

## Estructura del proyecto

- `ada.py`: CLI para indexar fotos, sugerir organización y ejecutar ADA.
- `agent_loop.py`: agente interactivo, parser de solicitudes y routing de skills.
- `models.py`: selección de proveedores y adaptadores para Ollama, OpenAI y Anthropic.
- `memory.py`: memoria persistente SQLite para tareas, conocimiento y procedimientos.
- `image_embedding.py`: embeddings visuales y de texto usados por el indexador.
- `ui_server.py` y `ui/`: interfaz web local.
- `skills/operations/`: ejecución de comandos y operaciones sobre archivos.
- `skills/photos/`: análisis, listado, organización y workflows de Lightroom.
- `skills/system/`: puente opcional con servidores MCP.
- `skills/data/`: consultas de bases SQLite en modo lectura.
- `agents/`: especialistas y coordinadores multiagente.
- `scripts/`: scripts auxiliares y pruebas manuales.
- `docs/`: documentación histórica y notas internas del proyecto.

## Seguridad y permisos

Las skills de lectura no modifican archivos. Las operaciones de ejecución,
movimiento, copia, creación de carpetas y organización requieren confirmación
cuando `confirm_risky` está activo en `config.json`.

La skill `sqlite` abre bases en modo lectura. El puente MCP permanece desactivado
hasta que se configure explícitamente `mcp_servers`.

## Configuración

`config.json` define el modelo de conversación (`ollama_model`), el modelo
visual (`vision_model`), rutas de fotos, límites de ejecución, memoria y nivel
de confirmación. Los modelos remotos se habilitan mediante sus variables de
entorno correspondientes.

## Analizador de fotos

### Arquitectura multiagente

El análisis fotográfico se ejecuta mediante `MultiAgentCoordinator`. Los
especialistas independientes son:

- `TechnicalPhotoAgent`: decodificación RAW y métricas técnicas.
- `ContextPhotoAgent`: sujeto, contexto, estilo y coincidencia con la sesión.
- `PhotoReviewAgent`: combina resultados y produce una recomendación.

Los dos primeros corren en paralelo. El coordinador conserva los campos
anteriores (`technical`, `semantic`, `session_context`) para no romper clientes,
y además devuelve los resultados agrupados en `agents`. Para agregar un nuevo
especialista se registra en `AgentRegistry`; no hace falta duplicar memoria,
permisos ni conexión con modelos.

La skill `photos/analyze_photo.py` combina dos fuentes:

1. **Análisis local rápido:** Pillow y NumPy calculan enfoque mediante varianza
   del Laplaciano, luminancia media, clipping de sombras y altas luces, contraste,
   orientación y una puntuación general técnica.
2. **Análisis semántico opcional:** Ollama recibe la imagen y devuelve sujeto,
   contexto, estilo, feedback fotográfico, puntuación artística y una estimación
   de coincidencia con la sesión de la carpeta.

### Calibración RAW e ISO

Los RAW no se evalúan como si fueran JPG terminados. ADA lee el encabezado RAW
y, cuando existe, el XMP asociado para recuperar cámara, ISO, velocidad, apertura
y lente. Una subexposición con altas luces no recortadas recibe un margen de
recuperación, porque todavía puede revelarse desde el negativo digital. Ese
margen no se aplica si hay clipping importante en altas luces.

El riesgo de ruido se calcula por ISO y se incorpora al puntaje técnico. Los
perfiles de fabricante son priors iniciales y deliberadamente modestos: Sony
recibe una tolerancia algo mayor a ISO alto y Nikon una penalización ligeramente
mayor. No reemplazan la evidencia de la imagen ni pretenden afirmar que todos
los cuerpos de una marca rinden igual; deben calibrarse con fotos aceptadas y
rechazadas de cada cámara.

El análisis local no requiere descargar un modelo. La parte semántica requiere
Ollama y un modelo con visión, por ejemplo:

```bash
ollama pull qwen2.5vl:3b
```

La puntuación técnica es una ayuda consistente, no una verdad absoluta. La
coincidencia de sesión también usa confianza: nombres, carpeta y contexto visual
son evidencias, no una identificación definitiva de lugar o personas.

Uso desde Python:

```python
from skills.photos.analyze_photo import run

result = run({
    "path": "/ruta/a/imagen.jpg",
    "folder": "/ruta/a/sesion",
    "vision": False,
})
```

Uso desde ADA:

```text
Analizá la foto /ruta/a/imagen.jpg
```

Para lotes grandes, la skill `photos/select_photo_batch.py` hace una primera
selección local sin enviar miles de imágenes al modelo visual:

```text
Seleccioná las fotos de /ruta/al/evento y prepará una shortlist de 300
```

Cada archivo del lote invoca el mismo workflow multiagente que una foto
individual (`analyze_photo`). No existe un cupo fijo de seleccionadas: cada
foto queda `Seleccionada` o `Rechazada` según su propia revisión. Si se pide
XMP, el sidecar se escribe inmediatamente al terminar ese archivo, con rating
Lightroom, puntaje ADA y motivo. No mueve ni elimina archivos.

Con `vision=False` se obtiene únicamente el análisis técnico. Esto permite
probar la skill y procesar grandes carpetas aun cuando Ollama no esté activo.

## Pruebas

Las pruebas del analizador no necesitan red ni modelo visual: verifican imágenes
válidas, imágenes inexistentes, cálculo de métricas y carga recursiva de skills.

```bash
ADA/.venv/bin/python -m unittest discover -s tests -v
```
