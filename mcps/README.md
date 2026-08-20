# ADA - MCP (Model Context Protocol) Servidores Modulares

Cada servidor MCP propio cuenta con su **propia subcarpeta independiente** dentro de `mcps/`, permitiendo que cada uno crezca, incluya sus propios módulos, utilidades y tests sin mezclarse.

---

## 📁 Estructura Modular de `mcps/`

```text
mcps/
├── config.json                     # ⚙️ Archivo central mcpServers (estándar VS Code)
├── protocol.py                     # 🔌 Base de comunicación JSON-RPC 2.0 stdio
├── README.md
│
├── filesystem/                     # 📁 Servidor MCP de Archivos
│   ├── __init__.py
│   ├── server.py                   # Entrypoint ejecutable (python mcps/filesystem/server.py)
│   └── handlers.py                 # Lógica de listado, lectura, escritura y movimiento
│
├── web_search/                     # 🌐 Servidor MCP de Búsqueda Web
│   ├── __init__.py
│   ├── server.py                   # Entrypoint ejecutable (python mcps/web_search/server.py)
│   └── searcher.py                 # Cliente y parser de DuckDuckGo
│
├── photography/                    # 📷 Servidor MCP de Fotografía
│   ├── __init__.py
│   ├── server.py                   # Entrypoint ejecutable (python mcps/photography/server.py)
│   └── analyzer.py                 # Extracción EXIF y métricas de calidad
│
├── food/                           # 🍳 Servidor MCP de Recetas, Alacena y Compras
│   ├── __init__.py
│   ├── server.py                   # Entrypoint ejecutable (python mcps/food/server.py)
│   ├── inventory.py                # Alacena e inventario
│   ├── recipes.py                  # Recetas y perfiles dietarios
│   ├── shopping.py                 # Lista de compras inteligente
│   └── planner.py                  # Planificador semanal de comidas
│
├── git/                            # 🌿 Servidor MCP de Control de Versiones Git
│   ├── __init__.py
│   ├── server.py                   # Entrypoint ejecutable (python mcps/git/server.py)
│   └── manager.py                  # Status, log, diff, add, commit, branch, push, pull
│
└── system/                         # ⚡ Servidor MCP de Ejecución de Sistema
    ├── __init__.py
    ├── server.py                   # Entrypoint ejecutable (python mcps/system/server.py)
    └── runner.py                   # Ejecutor con validación de prefijos en allowlist
```

---

## ⚙️ Configuración en `mcps/config.json`

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "python",
      "args": ["mcps/filesystem/server.py"],
      "description": "Servidor MCP modular de archivos de ADA",
      "status": "active"
    },
    "web-search": {
      "command": "python",
      "args": ["mcps/web_search/server.py"],
      "description": "Búsqueda web en vivo mediante DuckDuckGo",
      "status": "active"
    },
    "photography": {
      "command": "python",
      "args": ["mcps/photography/server.py"],
      "description": "Análisis técnico de calidad de imágenes RAW/JPG y Lightroom",
      "status": "active"
    },
    "food": {
      "command": "python",
      "args": ["mcps/food/server.py"],
      "description": "Gestor de recetas, inventario de comida, lista de compras y alacena",
      "status": "active"
    },
    "system-runner": {
      "command": "python",
      "args": ["mcps/system/server.py"],
      "description": "Ejecutor de comandos en allowlist",
      "status": "active"
    },
    "google-gmail": {
      "type": "sse",
      "url": "https://mcp.googleapis.com/v1/gmail",
      "env": {
        "GMAIL_CLIENT_ID": "${GMAIL_CLIENT_ID}"
      },
      "description": "Servidor MCP oficial de Google Gmail vía SSE",
      "status": "active"
    },
    "sqlite-memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sqlite", "memory.db"],
      "description": "Servidor MCP de base de datos SQLite estándar",
      "status": "active"
    },
    "git": {
      "command": "python",
      "args": ["mcps/git/server.py"],
      "description": "Servidor MCP modular de control de versiones Git para ADA",
      "status": "active"
    }
  }
}
```
