# MCP System Runner

El servidor MCP **`mcps/system/`** permite ejecutar comandos y scripts de sistema de forma controlada mediante una lista blanca de prefijos autorizados (`DEFAULT_ALLOWED_PREFIXES`).

---

## 🛠️ Herramientas Expuestas

### `system.run_command`
- **Descripción**: Ejecuta un script o comando de sistema autorizado en la allowlist.
- **Riesgo**: `confirmation`.
- **Parámetros**:
  - `command` (string, requerido): Comando a ejecutar (ej: `git status`, `uptime`, `date`, `pytest`).
- **Prefijos Permitidos por Defecto**:
  `echo`, `ls`, `dir`, `git status`, `git log`, `uptime`, `whoami`, `date`, `pytest`, `python --version`.
