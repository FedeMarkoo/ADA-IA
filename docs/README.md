# ADA — Asistente local ligero

Carpeta de proyecto para tu asistente local llamado ADA. Contiene indexado de imágenes, búsqueda web y memoria local.

Montar como unidad (opcional):
- Para crear un punto de montaje simbólico en `/Volumes/ADA` y acceder como unidad montada:
```bash
mkdir -p /Volumes/ADA
ln -s "$HOME/Desktop/ADA" /Volumes/ADA/ADA
```

Instalación (macOS, CPU/MPS):
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r ADA/requirements.txt
python -m playwright install
```

Para habilitar el modelo local recomendado, instalá Ollama desde https://ollama.com y descargá un modelo chico:

```bash
ollama pull llama3.2:3b
ollama serve
```

ADA detecta Ollama en `http://127.0.0.1:11434`. Se puede cambiar el modelo o la URL en `config.json` o mediante `ADA_OLLAMA_URL`.

Uso:
```bash
cd ADA
python ada.py index --dir /ruta/a/fotos
python ada.py suggest --dir /ruta/a/fotos
python ada.py run
```
Prompt invocation (natural language):
```bash
# Heuristic commands parsed from a prompt
python ada.py prompt "Index the folder /Users/home/Desktop/Fotos"
python ada.py prompt "Suggest organization for /Users/home/Desktop/Fotos"
python ada.py prompt "Please find duplicates and move rejected images"
```

The `prompt` subcommand will try simple heuristics to detect actions (`index`, `suggest`, `run:`) and otherwise send the text to ADA's agent.

Durante el modo interactivo se puede usar `/models` para ver los proveedores disponibles, `/teach nombre: instrucciones` para guardar un procedimiento y `/mem list` para listar los procedimientos aprendidos. Las operaciones que ejecutan comandos o mueven archivos requieren confirmación.

Config: edita `config.json` para ajustar `max_threads`, `use_mps` y `mount_point`.

Estructura de skills y memorias:
- `ADA/skills/<category>/*.py` — código ejecutable de skills, agrupado por área.
- `ADA/docs/skills/<category>/*.md` — documentación legible y metadatos de cada skill.
- `ADA/docs/memory/summaries/` — Markdown con resúmenes humanos añadidos automáticamente.

## Visión original del proyecto

ADA debe evolucionar hacia un agente de IA local y general, al que el usuario pueda ir enseñándole cómo realizar tareas. La gestión de fotos es sólo uno de los primeros casos de uso, no el objetivo exclusivo del proyecto.

El agente debería poder:

- interpretar una solicitud y estimar su complejidad;
- elegir automáticamente el modelo más conveniente para cada tarea;
- usar un modelo local pequeño para conversaciones simples, clasificación, ejecución de scripts y generación de reportes;
- delegar tareas complejas —como diseñar un script nuevo, investigar o analizar información— a un modelo más grande, como ChatGPT o Claude;
- utilizar herramientas y skills reutilizables para ejecutar acciones concretas;
- aprender procedimientos a partir de instrucciones, ejemplos y resultados proporcionados por el usuario;
- guardar en memoria los procedimientos aprendidos, las decisiones tomadas y los resultados de las ejecuciones;
- pedir confirmación antes de mover, borrar o modificar archivos u otra información sensible.

## Arquitectura prevista

El flujo principal debería ser:

```text
mensaje del usuario
        ↓
agente / router
        ↓
clasificación y estimación de complejidad
        ↓
selección del modelo
        ↓
selección de herramientas o skill
        ↓
confirmación si la operación es riesgosa
        ↓
ejecución
        ↓
reporte del resultado
        ↓
memoria del procedimiento y del resultado
```

## Modelos

La idea es utilizar Ollama como backend local para los modelos pequeños. Así ADA puede resolver tareas rutinarias sin depender de un servicio externo. Para tareas que requieran mayor capacidad se podrán utilizar modelos remotos mediante las APIs de OpenAI, Anthropic u otros proveedores.

La selección no debería depender sólo del tipo de tarea, sino también de su complejidad, privacidad, costo y necesidad de herramientas. Por ejemplo:

- tarea simple: ejecutar un script existente y explicar si terminó correctamente → modelo local pequeño;
- tarea intermedia: adaptar un script conocido a otra carpeta o formato → modelo local o intermedio;
- tarea compleja: diseñar un procedimiento nuevo, depurar un problema difícil o hacer un análisis profundo → modelo grande como ChatGPT o Claude.

## Aprendizaje y skills

“Enseñar” a ADA significa convertir una instrucción o demostración en un procedimiento reutilizable. La memoria no debería limitarse a guardar el texto de una conversación: debería registrar qué tarea se quería resolver, qué pasos se usaron, qué parámetros requiere, qué permisos necesita y si la ejecución tuvo éxito.

Las skills son la forma concreta de darle capacidades al agente. Actualmente existen skills para organizar fotos y ejecutar comandos, pero el objetivo es que ADA pueda incorporar nuevos procedimientos sin quedar limitado a un único caso de uso.

### Herramientas generales

Para evitar una skill nueva por cada variación de una tarea, ADA usa herramientas composables. La principal es `skills/operations/files/filesystem.py`, que concentra operaciones de lectura (`list_files`, `list_dirs`, `search`) y escritura (`move_files`, `copy_files`, `mkdir`). Las escrituras requieren confirmación y devuelven un reporte verificable.

Las skills antiguas y especializadas se mantienen temporalmente por compatibilidad, pero los nuevos workflows deberían componerse con estas herramientas generales. Por ejemplo, listar fotos es `filesystem + list_files + filtro de extensiones`, mientras que agrupar archivos es `filesystem + move_files`.

## Estado actual

El código actual implementa un primer agente operativo:

- `ModelManager` selecciona entre Ollama, OpenAI y Anthropic según complejidad, privacidad y disponibilidad;
- existe un chat interactivo por terminal y una interfaz web;
- existe memoria SQLite persistente para tareas, procedimientos y documentos confiables;
- las herramientas generales se cargan dinámicamente;
- `filesystem` concentra operaciones de archivos y exige confirmación para escribir;
- `lightroom` conecta las reglas del proyecto con `gestor_fotos_lightroom.py`;
- la planificación de Lightroom usa simulación por defecto y separa plan, ejecución y reporte.
- las consultas de la base SQLite usan la tool `sqlite`, en modo solo lectura; `lightroom` queda reservado para analizar y ordenar archivos.

La carpeta `Fotos` no se modifica automáticamente durante la carga de conocimiento. Para operar sobre ella, ADA debe primero generar un plan simulado y luego recibir confirmación explícita. La memoria `ADA/ADA/memory.db` y otros artefactos heredados se conservan por compatibilidad, pero la base canónica configurada para ADA es `ADA/memory.db`.

## Conocimiento de Lightroom

`config.json` registra `REGLAS_GESTOR_FOTOS.md` como documento confiable. ADA lo carga en memoria como conocimiento de proyecto y lo incluye como contexto cuando la solicitud menciona Lightroom, RAW, XMP, rechazadas o colecciones.

La skill `lightroom` no reimplementa las reglas en el modelo. Delega en el script existente y ofrece estas capas:

- `plan` / `simulate`: ejecuta `organizar --simular` y no mueve archivos;
- `count` y `analyze`: consulta el gestor según sus modos existentes;
- `organize`, `mover`, `limpiar` y `recuperar`: requieren confirmación explícita;
- todos los modos devuelven stdout, stderr, código de salida y comando ejecutado.

## MCP

ADA incluye un puente MCP opcional en `mcp_client.py` y la skill `mcp`. Los
servidores no se activan automáticamente: deben declararse explícitamente en
`config.json`.

```json
"mcp_servers": {
  "mi-servidor": {"command": ["python3", "/ruta/al/servidor_mcp.py"]}
}
```

La skill permite listar herramientas con `list_tools: true` o llamar una
herramienta indicando `server`, `tool` y `arguments`. Las llamadas que no sean
de descubrimiento requieren confirmación. Esto permite conectar servicios
externos sin mezclar sus permisos con las herramientas locales.
