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
- routing de capabilities y motores locales;
- análisis multiagente de fotos RAW/JPG;
- selección por archivo y generación de XMP;
- detección conservadora de ráfagas;
- límites de CPU y concurrencia.

## Estado y trabajo pendiente

### Autonomía

- event bus persistente, scheduler con reintentos/prioridad/cancelación y
  watchers de carpetas: implementados en el worker autónomo;
- reglas de producto adicionales para detectar y procesar nuevas fotos:
  pendientes;
- modo simulación y auditoría de decisiones: implementados para capabilities
  con mutaciones; falta ampliar el dry-run a workflows compuestos.

### Compras y recetas

- lista de compras con cantidades, categorías y estados: implementada;
- inventario doméstico: implementado;
- recetario y sugerencias según ingredientes: implementados;
- planificación semanal y presupuesto: implementados;
- convertir recetas en listas de supermercado: implementado;
- recordatorios por horario o entrada a una zona autorizada.

### Móvil e integraciones

- prototipo de geofencing y notificaciones: reglas locales y webhook autenticado
  para Tasker/móvil implementados;
- adapter de Telegram con reintentos y auditoría: implementado; faltan comandos
  móviles adicionales;
- evaluación posterior de una app propia con Capacitor o React Native;
- despliegue permanente en Linux con servicios separados y backups.

## Principios

Local-first, privacidad por diseño, modularidad, observabilidad, reversibilidad,
confirmación humana y consumo responsable de CPU, memoria, batería y red.
