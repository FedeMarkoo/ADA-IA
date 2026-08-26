# 📚 Documentación Técnica de ADA-IA

Bienvenido a la documentación técnica de **ADA-IA**, un ecosistema modular de inteligencia artificial local, gestión de servidores MCP (*Model Context Protocol*), orquestación de modelos LLM con Ollama y herramientas especializadas.

---

## 🗂️ Índice General de Contenidos

### 🏗️ 1. Arquitectura y Diseño
- [**Visión General de Arquitectura**](architecture/overview.md): Principios de diseño, orquestador multiagente y router de intenciones.
- [**Estructura del Proyecto**](architecture/folder-structure.md): Jerarquía de carpetas en la raíz y límites de responsabilidad.
- [**Flujo de Datos y Razonamiento**](architecture/data-flow.md): Ciclo de vida de peticiones, políticas de seguridad y ejecución.
- [**Flujos completos con Mermaid**](architecture/complete-flows.md): Arquitectura, chat, seguridad, ciclo de vida y streaming SSE.

### 🔌 2. Servidores y Herramientas MCP (`mcps/`)
- [**Protocolo y Servidores MCP**](mcps/README.md): Estándar Stdio JSON-RPC 2.0, registro en `mcps/config.json` y catálogo de tools.
- [**MCP Photography & Lightroom**](mcps/photography.md): Análisis técnico, decodificación RAW, sidecars XMP, ráfagas y catálogo.
- [**MCP Food & Pantry**](mcps/food.md): Lista de compras, recetario inteligente, stock de alacena y presupuestos.
- [**MCP Filesystem**](mcps/filesystem.md): Operaciones seguras sobre el sistema de archivos con allowlist.
- [**MCP System Runner**](mcps/system.md): Ejecución de comandos del sistema con allowlist de prefijos.
- [**MCP Web Search**](mcps/web_search.md): Motor de búsqueda en vivo con DuckDuckGo.

### 🖥️ 3. Gestor Web y API (`dashboard/` & `ada/interfaces/web/`)
- [**Dashboard Gestor Web**](dashboard/README.md): Interfaz gráfica en React 19, monitoreo de salud y panel de control.
- [**Referencia de la API REST & SSE**](dashboard/api-reference.md): Endpoints de estado, chat en streaming, control de MCPs y diagnóstico.
- [**Guía funcional y capturas**](user-guide.md): Todas las pantallas, acciones y procedimientos de uso.
- [**Catálogo completo de funcionalidades**](functional-catalog.md): Capacidades, MCPs, rutas API y relación con el código.
- [**Aplicación de escritorio**](desktop.md): Shell GTK/WebKit, requisitos y ejecución.

### 🧠 4. Modelos de Lenguaje & Visión (`models/`)
- [**Catálogo de Modelos & Benchmarks**](models/README.md): Asignación de roles por hardware, catálogo y métricas de velocidad.
- [**Modelfiles Personalizados**](models/modelfiles.md): Definición de prompts de sistema y parámetros para Ollama.
- [**Routing multiproveedor y OmniRoute**](architecture/llm-routing-and-omnirouter.md): Comparación con Hermes, LiteLLM y OpenRouter; pools de credenciales, cuotas y arquitectura recomendada para ADA.

### 📱 5. Integración Telegram (`telegram/`)
- [**Servidor Independiente de Telegram**](telegram/README.md): Daemon desacoplado, polling de mensajes y reenvío seguro.

### 📖 6. Guías de Uso y Operaciones
- [**Inicio Rápido e Instalación**](guides/getting-started.md): Requisitos previos, entorno virtual y puesta en marcha.
- [**Desarrollo y Testing**](guides/development.md): Ejecución de tests con pytest, estándares de código y buenas prácticas.
- [**Operaciones y Diagnóstico**](guides/operations.md): Herramienta Health Doctor, auto-reparación y auditoría de eventos.

### 📜 7. Historial y Roadmap
- [**Changelog**](CHANGELOG.md): Registro de cambios por versión.
- [**Hoja de Ruta y Mejoras**](mejoras.md): Estado de features y visión a futuro.

---

## ⚡ Inicio Rápido (3 Comandos)

```bash
# 1. Instalar entorno y dependencias
python3 -m venv .venv && source .venv/bin/activate && pip install -e .

# 2. Ejecutar tests unitarios (100% pasando)
pytest

# 3. Iniciar el Gestor Web ADA Hub
python -m ada.interfaces.web.server
```
Accedé al gestor web en tu navegador: **[http://127.0.0.1:5005](http://127.0.0.1:5005)**.
