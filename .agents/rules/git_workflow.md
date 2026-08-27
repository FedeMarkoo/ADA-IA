# Regla de Oro: Flujo de Git y Commits a Main

## Regla Principal
- Cada cambio, mejora o corrección realizada debe organizarse en **commits atómicos y relevantes** con mensajes descriptivos.
- Una vez verificados los cambios mediante las pruebas correspondientes, **deben subirse inmediatamente a la rama `main`** (`git push origin main`).

## Pautas de Commits
1. Agrupar los cambios según su dominio o componente (e.g. `feat(mcp): ...`, `fix(telegram): ...`, `feat(monitoring): ...`, `fix(doctor): ...`).
2. Validar que la suite de pruebas pase (`pytest`) antes de realizar push.
3. No dejar cambios pendientes de commitear al finalizar las tareas solicitadas.
