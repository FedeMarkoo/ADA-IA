# ADA Skills

Cada skill tiene dos representaciones:

- `skills/<category>/<skill>.py`: código ejecutable (función `run(args)` que recibe un dict y devuelve dict).
- `docs/skills/<category>/<skill>.md`: documentación legible con metadata YAML frontmatter.

Ejemplo: `run_script` permite ejecutar comandos locales con timeout.

Las skills están agrupadas por área:

- `operations/execution`: ejecución controlada de comandos y scripts.
- `operations/files`: lectura, búsqueda, copia, movimiento y agrupación de archivos.
- `system`: integración con servicios y servidores MCP.
- `photos`: listado, organización y workflows de fotos/Lightroom.
- `data`: consultas de datos locales, como SQLite.

Las capacidades principales deben agregarse como herramientas generales, no
como una skill por cada frase posible:

- `filesystem`: lectura y escritura segura de archivos y carpetas.
- `lightroom`: workflow especializado que usa las reglas del proyecto y el
  gestor existente; planifica/simula antes de modificar `Fotos`.
- `run_script`: ejecución controlada de comandos con reporte.

Las skills antiguas se mantienen por compatibilidad con las pruebas existentes.
Los nuevos procedimientos deberían componerse con las herramientas generales
y documentarse en la memoria de ADA.
