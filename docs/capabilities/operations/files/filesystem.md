---
name: filesystem
description: Herramienta general para leer y modificar archivos y carpetas.
params:
  - action: list_files | list_dirs | search | move_files | copy_files | mkdir
  - dir: carpeta de origen
  - confirm: requerido para modificaciones
risk: variable
permissions: filesystem
---

Las operaciones de lectura no modifican datos. Las operaciones de escritura
requieren confirmación y devuelven un reporte con los cambios realizados.
