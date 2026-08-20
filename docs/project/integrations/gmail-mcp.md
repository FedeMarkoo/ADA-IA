# Gmail mediante MCP

ADA puede usar el servidor MCP remoto oficial de Gmail de Google en lugar de mantener una integración Gmail específica dentro del núcleo.

El endpoint es `https://gmailmcp.googleapis.com/mcp/v1` y actualmente expone herramientas para buscar hilos, leer mensajes/hilos, consultar etiquetas y crear borradores. El servidor de Gmail de Google está en Developer Preview.

## Configuración

1. Crear o seleccionar un proyecto de Google Cloud.
2. Habilitar Gmail API y Gmail MCP API.
3. Configurar OAuth 2.0 para el host MCP.
4. Obtener un access token válido y exportarlo en el entorno de ADA:

```bash
export GMAIL_MCP_ACCESS_TOKEN="..."
```

No guardar el token en `config.json`, `.vscode/mcp.json` ni Git.

El ejemplo de `config.example.json` ya incluye:

```json
"gmail": {
  "type": "http",
  "url": "https://gmailmcp.googleapis.com/mcp/v1",
  "headers": {
    "Authorization": "Bearer ${env:GMAIL_MCP_ACCESS_TOKEN}"
  }
}
```

La capability `gmail` usa ese mismo servidor para:

- `search` → `search_threads`
- `get_thread` → `get_thread`
- `create_draft` → `create_draft`

Crear borradores requiere `confirm: true`. ADA no implementa las operaciones Gmail internamente: delega la operación al MCP.

## Uso mediante la capability MCP genérica

También se puede invocar directamente el servidor configurado:

```json
{
  "server": "gmail",
  "tool": "search_threads",
  "arguments": {
    "query": "from:cliente@example.com newer_than:30d"
  }
}
```

Esto permite utilizar cualquier otra tool que Google agregue al servidor sin tener que modificar ADA.

## Seguridad

El token OAuth debe permanecer fuera del repositorio. El servidor remoto hereda los permisos y controles de acceso de Google Workspace asociados al usuario autenticado. Las acciones de escritura se mantienen detrás de confirmación explícita en ADA.
