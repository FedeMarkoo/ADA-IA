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
La configuración puede vivir en `config.json` bajo `mcp_servers`. ADA sólo
importa `.vscode/mcp.json` cuando `trust_workspace_mcp` está activado de forma
explícita en la configuración (o mediante `ADA_TRUST_WORKSPACE_MCP=1`). Mantener
el valor desactivado al abrir repositorios que no sean de confianza: un servidor
`stdio` puede ejecutar el comando declarado por el workspace.

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
resuelven desde el entorno de ADA tanto solas como incrustadas en otros valores
(`--token=${env:TOKEN}`). Las entradas `${input:NAME}` de VS Code no se resuelven
automáticamente: deben convertirse en variables de entorno o valores explícitos
antes de ejecutar ADA.

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
Los endpoints remotos deben usar HTTPS. HTTP sin cifrar sólo se permite para
loopback (`localhost`, `127.0.0.1` o `::1`), salvo opt-in explícito mediante
`allow_insecure_http` en la definición del servidor.

## Ejecución

La capability `mcp` puede recibir `servers`, `mcp_servers` o `mcpServers` para
facilitar la reutilización de una configuración existente. Primero puede usarse
`list_tools: true` para descubrir las herramientas y después `tool` + `arguments`
para ejecutar una de ellas.

Los servidores MCP son código externo y reciben los permisos que su propio
proceso requiera. ADA mantiene su política de confirmación para operaciones
riesgosas en cada invocación; confiar en un workspace sólo habilita la carga de
su definición y no elimina esa confirmación. El entrypoint `ada-mcp` también
encamina sus llamadas por el mismo motor de políticas.
