# Servidores y Herramientas MCP (*Model Context Protocol*)

ADA implementa y soporta el estándar abierto **Model Context Protocol (MCP)** desarrollado por Anthropic, permitiendo exponer y consumir herramientas mediante transporte Stdio JSON-RPC 2.0.

---

## ⚙️ Registro Canónico: [`mcps/config.json`](file:///home/fedemarkoo/.gemini/antigravity-ide/scratch/ADA-IA/mcps/config.json)

El archivo `mcps/config.json` sigue el formato estándar `mcpServers` compatible con VSCode, Claude Desktop, Antigravity y ADA:

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
      "description": "Servidor MCP oficial de Google Gmail vía SSE",
      "status": "active"
    },
    "sqlite-memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sqlite", "ada/memory.db"],
      "description": "Servidor MCP de base de datos SQLite estándar",
      "status": "active"
    }
  }
}
```

---

## 🛠️ Catálogo de Servidores Disponibles

| Servidor | Módulo | Herramientas Expuestas | Documentación |
| :--- | :--- | :--- | :--- |
| **`photography`** | `mcps/photography/` | 7 herramientas (RAW, XMP, ráfagas, lote, Lightroom) | [Ver detalle](photography.md) |
| **`food`** | `mcps/food/` | 3 herramientas (`food.shopping`, `food.recipes`, `food.inventory`) | [Ver detalle](food.md) |
| **`filesystem`** | `mcps/filesystem/` | 5 herramientas (`list_files`, `read_file`, `write_file`, `move_files`, `group_files`) | [Ver detalle](filesystem.md) |
| **`system-runner`** | `mcps/system/` | 1 herramienta (`system.run_command`) | [Ver detalle](system.md) |
| **`web-search`** | `mcps/web_search/` | 1 herramienta (`web_search.search`) | [Ver detalle](web_search.md) |
| **`google-gmail`** | Cloud SSE | `gmail.read_inbox` | Servidor Oficial Google |
| **`sqlite-memory`**| Node MCP | `sqlite.read_query` | Estándar SQLite MCP |
