# Auditoría UX/UI del gestor de ADA

Fecha: 21 de agosto de 2026  
Alcance: arquitectura de información, navegación, dashboard, operaciones, responsive, accesibilidad, lenguaje y sistema visual.

## Diagnóstico ejecutivo

El gestor anterior exponía casi toda la complejidad interna de ADA al mismo nivel. Era útil como consola de desarrollo, pero no como herramienta de operación diaria. El problema principal no era la estética: era la ausencia de una jerarquía clara entre observar, decidir, configurar y ejecutar acciones peligrosas.

La propuesta convierte el gestor en una interfaz de decisiones:

1. informa si ADA está disponible;
2. separa lo saludable de lo que requiere atención;
3. propone una acción concreta para cada pendiente;
4. deja el detalle técnico en la sección correspondiente;
5. mantiene las acciones globales infrecuentes fuera del camino principal.

## Hallazgos

### 1. Arquitectura de información — crítico

- La navegación mezclaba infraestructura (`Ollama`, `MCPs`), tareas (`Chat`), canales (`Telegram`) y datos (`Memoria`) en dos grupos poco descriptivos.
- Etiquetas como “Overview”, “Hub”, “Tools”, “Daemon” y “Lifecycle” combinaban español e inglés y exigían conocimiento técnico.
- “Chat”, una de las tareas más frecuentes, aparecía debajo de cuatro secciones de administración.
- Los badges contenían datos fijos (`19 tools`, `MCP Servers (5)`) aunque la API devolvía cantidades reales diferentes.

Decisión: reorganizar por intención — operar, configurar, canales y datos— y usar cantidades dinámicas.

### 2. Dashboard y jerarquía — crítico

- El resumen repetía el estado de los servicios en el healthcheck, las tarjetas de estadísticas y la matriz de control.
- Un sistema al 92% mostraba simultáneamente “Degradado” y “Todos los subsistemas operando”, una contradicción semántica.
- Siete comprobaciones saludables ocupaban más espacio que la única alerta relevante.
- Se mezclaban lectura y operación: iniciar, detener, reiniciar y limpiar competían visualmente dentro de la misma pantalla.
- Los modelos asignados estaban escritos de forma fija y podían diferir de la política real del backend.

Decisión: mostrar primero la conclusión, luego sólo los pendientes, después los tres servicios esenciales y finalmente recursos/modelos reales.

### 3. Seguridad operacional — alta

- “Reiniciar todo” estaba siempre visible y tenía más peso visual que las tareas habituales.
- Debug y warmup ocupaban la cabecera de todas las vistas aunque son acciones infrecuentes.
- La abundancia de botones de iniciar/detener/reiniciar aumentaba el riesgo de una acción accidental.

Decisión: agrupar acciones globales en un menú secundario; mantener lo destructivo diferenciado y fuera del flujo primario. Las acciones específicas permanecen en el módulo que administra el recurso.

### 4. Responsive — crítico

- A 390 px, la barra lateral conservaba unos 260 px y dejaba el contenido principal casi inutilizable.
- La cabecera y sus cuatro acciones se renderizaban fuera del viewport.
- Las grillas de tres y cuatro columnas no tenían breakpoints.
- Formularios, tarjetas y modales no se reordenaban para interacción táctil.

Decisión: navegación off-canvas, cabecera compacta, grillas adaptativas, acciones de ancho completo cuando corresponde y modales tipo hoja inferior en móvil.

### 5. Lenguaje y carga cognitiva — alta

- Títulos extensos como “Centro de Control de Servicios & Ciclo de Vida” no ayudaban a decidir.
- Los parámetros técnicos aparecían en la etiqueta principal (`num_thread`, `num_ctx`, `keep_alive`) en vez de como ayuda contextual.
- La interfaz abusaba de mayúsculas, emojis y badges, reduciendo su valor como señales.

Decisión: español consistente, títulos cortos, explicación concreta del efecto de cada opción y términos internos relegados al texto de ayuda.

### 6. Sistema visual — media/alta

- Brillos, gradientes, emojis multicolor y múltiples acentos competían con los estados reales.
- Hover elevaba casi todas las tarjetas aunque muchas no eran interactivas.
- El rojo se usaba tanto para modo debug como para peligro.
- La jerarquía se apoyaba demasiado en color y poco en estructura y texto.

Decisión: interfaz oscura más calma, bordes y superficies sobrias, azul para acciones, verde para disponibilidad, ámbar para atención y rojo reservado para error/peligro.

### 7. Accesibilidad — alta

- Faltaba un tratamiento global visible para foco de teclado.
- El estado activo del menú no exponía `aria-current`.
- Los toasts no tenían región viva.
- La navegación móvil no existía y las etiquetas de algunos controles no estaban asociadas.
- Los emojis variaban entre plataformas y producían nombres accesibles ruidosos.

Decisión: iconos SVG decorativos, foco consistente, landmarks y regiones etiquetadas, `aria-current`, `aria-live`, labels vinculados y soporte para `prefers-reduced-motion`.

## Nueva arquitectura

| Grupo | Secciones | Objetivo |
|---|---|---|
| Operar | Resumen, Conversar con ADA | Entender el estado y realizar la tarea principal |
| Configurar | Motor local, Modelos y roles, Herramientas | Administrar capacidades técnicas |
| Canales y datos | Telegram, Actividad y memoria, Preferencias | Gestionar entradas, trazabilidad y comportamiento |

## Cambios implementados

- Navegación renombrada, reagrupada y alimentada con datos reales.
- Nuevo resumen sin duplicación de estados.
- Alertas presentadas por excepción: lo saludable no tapa lo urgente.
- Acciones globales infrecuentes dentro de “Más acciones”.
- Header más compacto y contextual.
- Iconografía SVG consistente en la estructura principal.
- Nuevo lenguaje visual sin glow decorativo ni gradientes dominantes.
- Responsive completo desde 390 px, sin desborde horizontal.
- Navegación móvil con scrim, cierre explícito y cierre automático al navegar.
- Grillas, formularios, chat, modales y tablas adaptables.
- Etiquetas y ayudas de configuración de Ollama reescritas en lenguaje de efecto.
- Foco visible, reducción de movimiento, `aria-current` y toasts anunciables.
- Métricas del resumen obtenidas del estado real: herramientas, servidores, modelos, recursos y roles.

## Riesgos y siguientes validaciones

La siguiente iteración debería observar a usuarios reales haciendo cinco tareas: detectar por qué ADA no responde, iniciar Telegram, cambiar el modelo de chat, instalar un modelo y revisar una acción en auditoría. Las métricas recomendadas son tiempo hasta diagnóstico, clics, retrocesos, errores y confianza declarada.

También conviene reemplazar los `window.confirm` restantes por un diálogo propio que explique impacto y alcance (por ejemplo, tamaño liberado al borrar un modelo) y revisar cada vista interna con el mismo criterio de lenguaje aplicado al resumen y a Ollama.

