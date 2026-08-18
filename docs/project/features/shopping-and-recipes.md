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

La conversación y la memoria de ADA pueden recibir texto sobre compras y
recetas, pero todavía no existen skills estructuradas de lista, inventario ni
recetario. Tampoco está implementado el detector de ubicación.

## Dirección técnica

```text
mensaje, horario o ubicación → evento → lista/receta → recordatorio → confirmación
```

Tasker puede servir como primer prototipo móvil para geofencing y notificaciones.
La ubicación debería producir un evento mínimo como
`entered_zone(supermercado)`, sin enviar el recorrido completo. Pagos, pedidos
online y compras externas quedan fuera de la primera versión y siempre exigirían
confirmación explícita.
