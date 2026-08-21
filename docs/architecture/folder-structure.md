# Estructura del Proyecto y Carpetas

El repositorio está organizado en carpetas independientes en la raíz, evitando acoplamientos innecesarios.

---

## 📁 Árbol de Directorios Principal

```text
ADA-IA/
├── README.md               # 📖 Descripción general e inicio rápido
├── pyproject.toml          # 📦 Definición de paquetes y dependencias (PEP 517/621)
│
├── ada/                    # 🤖 Núcleo del Asistente Inteligente
│   ├── config.json         # Configuración del agente y rutas permitidas
│   ├── memory.db           # Base de datos SQLite (memoria, sesiones, auditoría)
│   ├── application/        # Servicios de aplicación (Agent, Router, Planner, Doctor)
│   ├── domain/             # Contratos de dominio y reglas de negocio
│   ├── infrastructure/     # Adaptadores (Persistencia, Recursos, Integraciones)
│   ├── interfaces/         # API Web Flask/REST y CLI
│   ├── mcps/               # Gestor e introspección de herramientas MCP (MCPManager)
│   ├── models/             # Catálogo y benchmark de modelos
│   ├── ollama/             # Cliente HTTP local para Ollama
│   └── agents/             # Coordinador multiagente y agentes fotográficos
│
├── dashboard/              # 🖥️ Gestor Web SPA (Frontend React 19)
│   ├── index.html          # Shell HTML con carga de fuentes Inter/Outfit
│   ├── app.js              # Controlador SPA completo en React 19
│   └── styles.css          # Sistema de diseño dark-theme con tokens CSS
│
├── mcps/                   # 🔌 Servidores MCP Modulares e Independientes
│   ├── config.json         # Registro canónico mcpServers
│   ├── protocol.py         # Servidor base Stdio JSON-RPC 2.0
│   ├── photography/        # Análisis RAW, sidecars XMP, ráfagas y Lightroom
│   ├── food/               # Compras, recetario, stock de alacena y presupuestos
│   ├── filesystem/         # Operaciones seguras sobre archivos con allowlist
│   ├── system/             # Ejecución de comandos del sistema
│   └── web_search/         # Búsqueda en vivo DuckDuckGo
│
├── models/                 # 🧠 Modelos de Ollama, Modelfiles y Benchmarks
│   ├── catalog.json        # Catálogo de modelos y asignación de roles
│   ├── benchmarks.json     # Historial de benchmarks de velocidad
│   └── modelfiles/         # Modelfiles personalizados (Modelfile.ada, Modelfile.vision)
│
├── telegram/               # 📱 Servidor / Bot Independiente de Telegram
│   ├── bot.py              # Daemon long-polling desacoplado
│   └── README.md           # Guía de ejecución del servidor de Telegram
│
├── tests/                  # 🧪 Suite de Pruebas Automatizadas (pytest)
│   ├── test_photo_analysis.py
│   ├── test_food.py
│   ├── test_modular_packages.py
│   ├── test_telegram.py
│   └── ... (21 archivos de tests)
│
└── docs/                   # 📖 Documentación Técnica Completa
```

---

## 🎯 Límites de Responsabilidad

- **`ada/`** no contiene código de servidores MCP ni lógica de interfaces específicas (como Telegram). Expone endpoints REST y consume las herramientas a través de `mcps/`.
- **`mcps/`** es agnóstico a ADA: cada subcarpeta contiene un servidor MCP estándar que puede conectarse a cualquier cliente compatible (VSCode, Claude Desktop, Antigravity, ADA).
- **`dashboard/`** es una aplicación cliente estática servida por el backend REST de ADA.
- **`telegram/`** es un cliente que se comunica exclusivamente mediante llamadas HTTP al endpoint `/api/chat`.
