# Mejora MEM-02 — MCP de gestión de memoria

## Objetivo

Permitir que ADA gestione su memoria persistente mediante herramientas MCP explícitas, con el mismo contrato que usa el resto del runtime y con defensa en profundidad para las mutaciones.

## Herramientas

| Tool | Operación | Confirmación |
|---|---|---|
| `memory.search` | Consulta por texto, capa y límite | No |
| `memory.add` | Agrega un recuerdo con contenido, capa y metadatos | Sí |
| `memory.update` | Modifica contenido, capa o metadatos por `id` | Sí |
| `memory.delete` | Elimina un recuerdo por `id` | Sí |

Las capas admitidas son `note`, `short_term`, `episodic`, `semantic`, `profile` y `knowledge`. El MCP devuelve ids y metadatos para que ADA pueda confirmar que modificó el recuerdo correcto.

## Seguridad y privacidad

- Las operaciones de escritura, modificación y eliminación exigen `_confirmed` en `MCPManager.execute_tool`.
- El servidor reutiliza `Memory`, por lo que conserva WAL, conexión por thread y cifrado Fernet configurado.
- La consulta limita resultados a 50 y no expone el contenido cifrado almacenado en SQLite: lo descifra únicamente dentro del proceso autorizado.
- El registro se descubre en el catálogo MCP para que el router pueda seleccionarlo; las mutaciones siguen fuera de las rutas automáticas sin confirmación.

## Checklist

- [x] Servidor MCP `memory` registrado por defecto.
- [x] Agregar, modificar, eliminar y consultar recuerdos.
- [x] Confirmación obligatoria para mutaciones.
- [x] Tests de descubrimiento y ciclo CRUD.
