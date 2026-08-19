# Compras y recetas

Este es un objetivo funcional de ADA todavía pendiente de implementación
completa. El asistente debería mantener una lista de compras, inventario
opcional, recetas y planificación de comidas.

## Capacidades objetivo

- agregar, editar, marcar y cancelar productos;
- guardar cantidades, unidades, categorías y prioridades;
- sugerir recetas según ingredientes disponibles;
- convertir una receta o plan semanal en lista de supermercado;
- considerar porciones, restricciones, presupuesto y preferencias;
- recordar una compra cuando el usuario entra a una zona autorizada;
- actualizar la lista desde un mensaje o notificación.

## Estado actual

La primera versión implementada incluye una capability local persistente para
lista de compras y recetario. Desde la web o Telegram se pueden agregar,
listar, marcar como comprados y quitar productos; guardar recetas simples,
listarlas, sugerirlas por ingredientes y convertir sus ingredientes en una
lista de compras. Los datos viven en las tablas `food_shopping` y
`food_recipes` de la misma SQLite de ADA.

El inventario, el presupuesto, la planificación semanal y el detector de
ubicación siguen pendientes. Tampoco se realizan pedidos ni pagos externos.

## Configuración dinámica de IA

El comportamiento no depende únicamente de texto en Python. ADA mantiene en
SQLite las tablas `router_catalog` y `prompt_templates`. La primera describe
las acciones disponibles, keywords de fallback y sus descripciones; la segunda contiene los prompts
versionables del router, del clasificador de comida, del verificador de
compras y del asesor culinario.

Los contratos JSON que Ollama debe respetar viven en `json_schemas` (`router`,
`food`, `food_verify` y `food_reply`). También pueden actualizarse sin tocar el
código mediante `Memory.upsert_json_schema()`.

Al iniciar, ADA crea los valores predeterminados solo si no existen. Esto
permite editar un prompt o desactivar una acción sin modificar el código. El
router valida contra las acciones habilitadas en `router_catalog`; una acción
ausente o desactivada no puede ser ejecutada.

### Ejemplos por Telegram

```text
agregá 2 litros de leche a la lista
mostrame la lista de compras
marcá leche como comprada
guardá receta tortilla: huevo, papa, cebolla; dorar todo
qué puedo cocinar con papa, huevo
pasá los ingredientes de tortilla a la lista
```

## Diseño inteligente

Las solicitudes abiertas se interpretan con Ollama y un JSON Schema cerrado,
no con un diccionario de frases. Si la clasificación general es ambigua, ADA
ejecuta una segunda clasificación semántica específica de comida.

El asesor recibe el perfil de gustos, el catálogo local y los últimos mensajes
del usuario. Su respuesta se solicita dentro de un objeto JSON con un único
campo `reply`, para evitar razonamientos internos visibles. Las mutaciones de
compras (`add`, `check` y `remove`) pasan además por una verificación semántica;
una recomendación como “dame otra opción” no debe modificar la lista.

Si Ollama no responde, ADA usa el recetario local como fallback. Los timeouts
son `router_timeout` y `food_advisor_timeout` (45 segundos por defecto).

## Diagnóstico

Con `serve -debug`, ADA crea un log con el timestamp de inicio en
`/Users/home/Desktop/logs/ada-debug-YYYYMMDD-HHMMSS.log`. Incluye el mensaje de
Telegram, la intención, la respuesta cruda del router, la verificación de
mutaciones, la respuesta del asesor y los errores.

- `ADA intent action=food food_action=advise`: llegó al asesor culinario.
- `food mutation verification ... allow=False`: bloqueó una compra ambigua.
- `food advisor failed: timed out`: se usó el catálogo local.
- `task type=null`: cayó al chat general, fuera del flujo culinario.

## Dirección técnica

```text
mensaje, horario o ubicación → evento → lista/receta → recordatorio → confirmación
```

Tasker puede servir como primer prototipo móvil para geofencing y notificaciones.
La ubicación debería producir un evento mínimo como
`entered_zone(supermercado)`, sin enviar el recorrido completo. Pagos, pedidos
online y compras externas quedan fuera de la primera versión y siempre exigirían
confirmación explícita.
