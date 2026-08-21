# Visión General de la Arquitectura

ADA-IA está diseñado como un **asistente de inteligencia artificial personal, autónomo y local**, optimizado para ejecutarse en hardware local con soberanía total de datos y desacople de componentes.

---

## 🏛️ Principios Fundamentales

1. **Local-First & Privacidad Absoluta**:
   - Todo el procesamiento de razonamiento y visión por computadora se ejecuta de forma local mediante **Ollama** y modelos abiertos (`llama3.2`, `llava`, `qwen2.5-coder`).
   - La persistencia de memoria episódica, semántica y transaccional se gestiona en **SQLite** local (`ada/memory.db`).

2. **Arquitectura Desacoplada y Modular**:
   - Cada componente del sistema es independiente:
     - **`ada/`**: Núcleo del agente (Router, Políticas, Planificador, Memoria).
     - **`mcps/`**: Servidores de herramientas estandarizados con el protocolo MCP.
     - **`dashboard/`**: Interfaz de control y gestión en React 19.
     - **`models/`**: Definición de catálogo y Modelfiles.
     - **`telegram/`**: Bot y adaptador de mensajería externo.

3. **Orquestación Multiagente**:
   - Para tareas complejas (como el culling y análisis fotográfico), ADA instancia agentes especialistas coordinados por un `MultiAgentCoordinator` con control de presupuesto de CPU y concurrencia.

4. **Seguridad y Políticas de Ejecución**:
   - Las operaciones destructivas o con efectos colaterales (mover archivos, ejecutar comandos) requieren confirmación explícita (`confirm_risky=True`) y respetan una lista estricta de rutas autorizadas (`allowed_roots`).

---

## 🧩 Componentes del Ecosistema

```text
               ┌───────────────────────────────┐
               │    Cliente Web (Dashboard)    │
               │   o Bot Externo (Telegram)    │
               └──────────────┬────────────────┘
                              │ HTTP REST / SSE
                              ▼
               ┌───────────────────────────────┐
               │     ADA REST API Server       │
               │   (ada.interfaces.web.server) │
               └──────────────┬────────────────┘
                              │
               ┌──────────────▼────────────────┐
               │    Intent Router & Planner    │
               │  (ada.application.router)     │
               └───────┬──────────────┬────────┘
                       │              │
        ┌──────────────▼───┐     ┌────▼──────────────┐
        │  Ollama Runtime  │     │   MCP Manager     │
        │ (Llama3.2/LLaVA) │     │ (mcps.manager)    │
        └──────────────────┘     └────┬──────────────┘
                                      │ JSON-RPC Stdio
                     ┌────────────────┴────────────────┐
                     │                                 │
            ┌────────▼────────┐               ┌────────▼────────┐
            │ mcps/photography│               │    mcps/food    │
            │ mcps/filesystem │               │   mcps/system   │
            └─────────────────┘               └─────────────────┘
```
