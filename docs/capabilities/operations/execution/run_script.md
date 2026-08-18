---
name: run_script
description: Ejecuta un comando shell con timeout y devuelve stdout/stderr.
params:
  - command: string (requerido) — comando a ejecutar
  - timeout: integer (opcional, default 30)
risk: medium
permissions: filesystem, subprocess
examples:
  - run: run: ls -la
---

Run `run_script` para automatizar tareas simples como mover archivos, ejecutar scripts de ordenamiento, etc.
