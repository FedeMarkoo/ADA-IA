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

ADA acepta definiciones de servidores compatibles con el formato de VS Code.
La configuración puede vivir en `config.json` bajo `mcp_servers` o copiarse desde
`.vscode/mcp.json` usando la sección `servers`.

## Servidores locales

```json
{
  "servers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "~/Desktop"],
      "env": {},
      "cwd": "~"
    }
  }
}
```

Se soportan `command`, `args`, `env` y `cwd`. Las variables `${env:NAME}` se
resuelven desde el entorno de ADA. Las entradas `${input:NAME}` de VS Code no se
resuelven automáticamente: deben convertirse en variables de entorno o valores
explícitos antes de ejecutar ADA.

## Servidores remotos

```json
{
  "servers": {
    "mi-servidor": {
      "type": "http",
      "url": "https://example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${env:MCP_TOKEN}"
      }
    }
  }
}
```

El transporte HTTP usa JSON-RPC sobre Streamable HTTP y conserva el
`Mcp-Session-Id` cuando el servidor lo entrega. También acepta respuestas
`text/event-stream` de servidores que entreguen el resultado mediante SSE.

## Ejecución

La capability `mcp` puede recibir `servers`, `mcp_servers` o `mcpServers` para
facilitar la reutilización de una configuración existente. Primero puede usarse
`list_tools: true` para descubrir las herramientas y después `tool` + `arguments`
para ejecutar una de ellas.

Los servidores MCP son código externo y reciben los permisos que su propio
proceso requiera. ADA mantiene su política de confirmación para operaciones
riesgosas; configurar un MCP no debe interpretarse como una autorización para
eliminar esa protección.
