# ADA

ADA es un asistente local, multiagente y orientado a la autonomía controlada.
Combina conversación, memoria persistente, capabilities ejecutables y motores locales
para ayudar con archivos, fotografías, organización, compras y futuras tareas
basadas en eventos.

## Objetivo

ADA no debe depender únicamente de prompts manuales. La dirección del proyecto
es evolucionar hacia un asistente que pueda recibir eventos autorizados,
interpretarlos, crear tareas, usar el agente o motor adecuado, pedir
confirmación cuando corresponda y registrar qué hizo y por qué.

Los principios son local-first, privacidad, modularidad, trazabilidad,
reversibilidad y uso responsable de CPU, memoria, batería y red.

## Capacidades actuales

- chat local por web y CLI;
- entrada opcional por Telegram mediante el mismo endpoint interno que la web;
- memoria persistente SQLite;
- routing de capabilities y arquitectura multiagente;
- motores locales mediante Ollama;
- análisis fotográfico RAW/JPG con feedback de fotógrafo;
- selección de lotes y generación de XMP para Lightroom;
- detección conservadora de ráfagas;
- herramientas para archivos, ejecución controlada, SQLite y MCP;
- límites de concurrencia y CPU para no saturar el equipo.

## Estructura del repositorio

```text
ADA/
├── docs/         documentación separada por responsabilidad
│   ├── project/  producto, arquitectura, funcionalidades y roadmap
│   └── capabilities/ contratos y uso de capacidades individuales
├── src/ada/      código de aplicación, agentes, capabilities e infraestructura
├── tests/        pruebas automatizadas
└── ui/           interfaz web
```

## Índices de documentación

- [Documentación general](docs/README.md)
- [Objetivo y roadmap](docs/project/roadmap.md)
- [Arquitectura](docs/project/architecture/overview.md)
- [Estructura de carpetas](docs/project/architecture/folder-structure.md)
- [Análisis de fotos](docs/project/features/photo-analysis.md)
- [XMP y ráfagas](docs/project/features/xmp-and-bursts.md)
- [Compras y recetas](docs/project/features/shopping-and-recipes.md)
- [Telegram y Ollama](docs/project/integrations/telegram-and-ollama.md)
- [Operación y recursos](docs/project/operations.md)
- [Documentación de capabilities](docs/capabilities/README.md)

## Instalación y ejecución

```bash
python3 -m venv .venv
python3 -m pip install -e '.[dev]'
ada serve
```

En Windows usá `.venv\\Scripts\\python.exe` y `.venv\\Scripts\\pip.exe` en lugar
de los comandos POSIX. Copiá `config.example.json` a `config.json` y ajustá las
rutas locales; `config.json` no se versiona.

La interfaz queda disponible en `http://127.0.0.1:5005/`.

Para abrir ADA como una aplicación independiente, sin iniciar Chrome:

```bash
ada desktop
```

En Linux, la ventana usa el WebKitGTK del sistema y levanta la misma interfaz
web/API local. Si faltan los componentes gráficos, instalalos con:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1
```

La web sigue disponible en `http://127.0.0.1:5005/` cuando usás `ada serve`.

Para usar el servidor ASGI desde el CLI: `ada serve --asgi`.
También podés definir `web_framework: "asgi"` en la configuración; Flask queda
disponible como fallback con `ADA_WEB_FRAMEWORK=flask`.

El proveedor activo y los modelos se configuran en `config.json`. Por ejemplo,
la configuración inicial usa un proveedor local con estos modelos:

```bash
ollama pull llama3.2:3b
ollama pull qwen2.5vl:3b
```

El análisis técnico puede ejecutarse sin modelo visual; el análisis semántico de
fotos necesita un modelo con visión.

La interfaz ASGI opcional se inicia con:

```bash
python3 -m uvicorn ada.interfaces.web.asgi:create_app --factory --host 127.0.0.1 --port 5006
```

Para cambiar el proveedor conversacional, modificá `engine_provider` y la
sección correspondiente (`models` o `gpt4all`) en `config.json`. Las interfaces
y el router no necesitan cambios.

## Pruebas

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/pre-commit run --all-files
```

La memoria se puede respaldar sin copiar manualmente el archivo WAL:

```bash
.venv/bin/ada backup --path ~/Desktop/ada-backups/memory.db
```

## Seguridad y datos

Las acciones que mueven, copian, crean o eliminan archivos requieren
confirmación. Los tokens de servicios externos deben configurarse mediante
variables de entorno y nunca guardarse en Git. Ollama y la API local no deben
exponerse directamente a internet.

Las bases SQLite, modelos descargados, entornos virtuales y archivos de prueba
locales están excluidos del repositorio mediante `.gitignore` cuando
corresponde.

Para autonomía controlada, configurá `watch_folders`, ejecutá
`ada-autonomous` y revisá la auditoría mediante `/api/audit`. Las acciones
externas requieren confirmación y las operaciones de archivos devuelven un
manifiesto utilizable por la acción `undo`.

Las reglas evento→acción se configuran en `event_rules`; por defecto solo se
ejecutan automáticamente acciones no riesgosas. Las acciones sensibles quedan
como propuestas auditadas hasta recibir confirmación explícita.
