# 🤖 05. Multiagente y MCPs

## Estado de Implementación

| ID | Mejora / Corrección | Estado | Commit |
|---|---|---|---|
| MCP-01 | Transición de capabilities in-process a servidores MCP estándar | ✅ Implementado | `05fa633` |
| MCP-02 | 7 Servidores MCP propios: `filesystem`, `photography`, `food`, `git`, `system`, `transport`, `web-search` | ✅ Implementado | `5e34825` |
| MCP-03 | Soporte para servidores MCP oficiales de Google (Drive, Gmail, Calendar) vía SSE | ✅ Implementado | `da2ce19` |
| MCP-04 | Detección y validación de schemas de herramientas MCP antes de invocar | ✅ Implementado | `da2ce19` |

---

## Catálogo de Servidores MCP Activos

| Servidor | Transporte | Rol |
|---|---|---|
| `filesystem` | stdio / python | Lectura, búsqueda y gestión de archivos con allowlist |
| `photography` | stdio / python | Análisis de calidad RAW/JPG, detección de ráfagas y XMP |
| `food` | stdio / python | Inventario de alacena, recetas, planificación y presupuesto |
| `git` | stdio / python | Operaciones estructuradas de Git sin comandos inseguros |
| `web-search` | stdio / python | Búsqueda en Google, DuckDuckGo y Brave |
| `transport` | stdio / python | Alertas en vivo de trenes y transporte público |
| `system-runner` | stdio / python | Ejecución de comandos pre-autorizados en allowlist |
| `google-gmail` | sse / remote | Integración oficial de Gmail |
| `google-drive` | sse / remote | Integración oficial de Google Drive |
| `google-calendar`| sse / remote | Integración oficial de Google Calendar |
