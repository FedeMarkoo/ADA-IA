---
name: mcp
description: Descubre y ejecuta herramientas de servidores MCP configurados explícitamente.
params:
  - server: nombre del servidor configurado
  - tool: nombre de la herramienta MCP
  - arguments: objeto de argumentos
  - list_tools: listar herramientas disponibles
risk: variable
permissions: subprocess, external-tool
---

Los servidores MCP deben declararse explícitamente en `config.json`.
