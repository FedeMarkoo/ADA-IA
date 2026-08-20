# Lightroom MCP

Lightroom is exposed as a standalone MCP server for external clients. The
existing ADA capability remains the canonical implementation and this server
delegates to it, so there is only one path containing execution and safety
logic. ADA itself continues to call that capability directly.

The server loads ADA's configuration independently. It validates `root` and
`only_route` against `allowed_roots`, accepts only the configured
`lightroom_script` (or entries in `lightroom_allowed_scripts`), bounds the
subprocess timeout, and records every call in ADA's `audit_log`. These checks
also apply when VS Code or another MCP host invokes the server without ADA's
agent policy in front of it.

`allowed_roots` debe contener al menos una raíz. Una
`lightroom_allowed_scripts` vacía deshabilita la ejecución; para habilitarla hay
que declarar la ruta exacta del script autorizado.

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

The server delegates execution to the existing, tested
`gestor_fotos_lightroom.py` flow. The existing capability and its safety
behavior remain authoritative; this PR adds an MCP transport/interface without
creating a second implementation.

## Architecture

```text
VS Code / external MCP client
  |
  v
Lightroom MCP (stdio + policy + audit)
  |
  v
ADA Lightroom capability (canonical adapter)
  |
  v
gestor_fotos_lightroom.py
  |
  +--> RAW/JPG/XMP filesystem
  +--> limpieza_lightroom.sqlite3
```

This is intentionally a first extraction step. Future work can move the Lightroom domain/service code into a separately publishable package/repository while keeping this MCP contract stable.
