# Objetivo y roadmap

## Objetivo

ADA debe evolucionar de un chat local a un compañero autónomo, privado y
multiagente. Debe observar eventos autorizados, decidir si una acción es útil,
ejecutarla con límites de recursos y explicar qué ocurrió.

La autonomía debe ser controlada: eventos y reglas explícitas, confirmación para
acciones riesgosas, memoria persistente, auditoría y posibilidad de pausar o
revocar tareas.

## Capacidades actuales

- conversación web y CLI;
- memoria SQLite;
- routing de skills y motores locales;
- análisis multiagente de fotos RAW/JPG;
- selección por archivo y generación de XMP;
- detección conservadora de ráfagas;
- límites de CPU y concurrencia.

## Trabajo pendiente

### Autonomía

- event bus persistente;
- scheduler con reintentos, prioridad, cancelación y bloqueo por lote;
- watcher de carpetas para detectar nuevas fotos;
- modo simulación y auditoría de decisiones.

### Compras y recetas

- lista de compras con cantidades, categorías y estados;
- inventario doméstico opcional;
- recetario y sugerencias según ingredientes;
- planificación semanal y presupuesto;
- convertir recetas en listas de supermercado;
- recordatorios por horario o entrada a una zona autorizada.

### Móvil e integraciones

- prototipo de geofencing y notificaciones con Tasker;
- adaptador de Telegram para texto e imágenes;
- evaluación posterior de una app propia con Capacitor o React Native;
- despliegue permanente en Linux con servicios separados y backups.

## Principios

Local-first, privacidad por diseño, modularidad, observabilidad, reversibilidad,
confirmación humana y consumo responsable de CPU, memoria, batería y red.
