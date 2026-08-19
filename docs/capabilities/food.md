# Food: compras y recetas

Capability: `food`.

Recibe un objeto con `domain` (`shopping` o `recipes`) y `action`. La interfaz
web y Telegram convierten el lenguaje natural a este contrato; la capability
no depende de Telegram.

Acciones soportadas:

- compras: `add`, `list`, `check`, `remove`;
- recetas: `save`, `list`, `get`, `suggest`;
- integración: `recipe_to_shopping`.

El almacenamiento usa la SQLite configurada por ADA. Agregar o quitar
productos y guardar recetas es reversible desde la conversación, pero no hay
compras online ni pagos.

## Fuente de preferencias

`config.json` apunta a `food_profile`, normalmente:

```text
/Users/home/Downloads/perfil_comidas_recetas_fede.md
```

ADA incorpora ese archivo como conocimiento y siembra sus secciones de recetas
en `food_recipes`. El archivo de preferencias es la fuente editable; las
recetas importadas no reemplazan las que el usuario agregue desde ADA.

Los prompts y el catálogo de acciones se administran en `prompt_templates` y
`router_catalog` dentro de la misma base. Se pueden actualizar mediante
`Memory.upsert_prompt_template()`; al reiniciar ADA, el router los utiliza sin
recompilar la aplicación. Las keywords del fallback también se almacenan como
JSON en `router_catalog.keywords`. Los contratos de salida de Ollama se
administran en `json_schemas` y se pueden actualizar con
`Memory.upsert_json_schema()`.
