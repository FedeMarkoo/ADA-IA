# ADA Skills

Cada skill tiene dos representaciones:

- `src/ada/capabilities/<category>/<capability>.py`: código ejecutable (función `run(args)` que recibe un dict y devuelve dict).
- `docs/skills/<category>/<skill>.md`: documentación legible con metadata YAML frontmatter.

Ejemplo: `run_script` permite ejecutar comandos locales con timeout.

Las capabilities están agrupadas por área:

- `system`: ejecución controlada, integración MCP y servicios del sistema.
- `files`: lectura, búsqueda, copia, movimiento y agrupación de archivos.
- `photography`: análisis, organización y workflows de fotos/Lightroom.
- `data`: consultas de datos locales, como SQLite.

Las capacidades principales deben agregarse como herramientas generales, no
como una capability por cada frase posible:

- `filesystem`: lectura y escritura segura de archivos y carpetas.
- `lightroom`: workflow especializado que usa las reglas del proyecto y el
  gestor existente; planifica/simula antes de modificar `Fotos`.
- `run_script`: ejecución controlada de comandos con reporte.

Cada capability debe tener un contrato claro y delegar las reglas de negocio a
`domain/` o los workflows de `application/`. Los nuevos procedimientos deberían
componerse con estas herramientas y documentarse en la memoria de ADA.
