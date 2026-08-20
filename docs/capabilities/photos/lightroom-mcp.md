# Lightroom MCP

Lightroom is exposed as a standalone MCP server so ADA can consume photo-management operations through the same MCP interface used for other external tools.

## Run locally

After installing ADA:

```bash
ada-lightroom-mcp
```

The server uses stdio and can be configured in `.vscode/mcp.json` or ADA's MCP configuration:

```json
{
  "servers": {
    "lightroom": {
      "type": "stdio",
      "command": "ada-lightroom-mcp"
    }
  }
}
```

When running from a source checkout, the equivalent command is:

```json
{
  "servers": {
    "lightroom": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "ada.interfaces.lightroom_mcp_server"]
    }
  }
}
```

## Tools

| Tool | Mutates files? | Purpose |
| --- | --- | --- |
| `lightroom_count_photos` | No | Count the photo inventory. |
| `lightroom_analyze` | No | Analyze the current photo tree and SQLite state. |
| `lightroom_plan` | No | Produce an organization plan. |
| `lightroom_simulate` | No | Simulate organization without writing files. |
| `lightroom_apply` | **Yes** | Apply the organization plan. Requires `confirm: true`. |
| `lightroom_recover` | **Yes** | Recover organization state. Requires `confirm: true`. |

The server delegates execution to the existing, tested `gestor_fotos_lightroom.py` flow. The existing rules and safety behavior remain authoritative; this PR separates the MCP transport/interface from ADA's agent process without rewriting the photo-management algorithm.

## Architecture

```text
ADA
  |
  | MCP client
  v
Lightroom MCP (stdio)
  |
  v
gestor_fotos_lightroom.py
  |
  +--> RAW/JPG/XMP filesystem
  +--> limpieza_lightroom.sqlite3
```

This is intentionally a first extraction step. Future work can move the Lightroom domain/service code into a separately publishable package/repository while keeping this MCP contract stable.
