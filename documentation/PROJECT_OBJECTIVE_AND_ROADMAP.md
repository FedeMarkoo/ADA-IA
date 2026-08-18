# ADA: objetivo del proyecto y dirección de desarrollo

Este documento transforma la conversación inicial del proyecto en una guía
común para tomar decisiones técnicas. El objetivo no es construir solamente un
chat que responde prompts: ADA debe convertirse en un compañero local,
proactivo y multiagente, capaz de observar señales autorizadas, decidir si una
acción es útil, ejecutarla con límites y mantener memoria de lo ocurrido.

## Objetivo principal

Construir una asistente personal autónoma y privada que:

- funcione principalmente con motores locales;
- pueda conversar desde la aplicación y, eventualmente, desde Telegram o
  WhatsApp mediante integraciones autorizadas;
- detecte eventos o cambios relevantes sin que el usuario tenga que escribir un
  prompt cada vez;
- ejecute procedimientos conocidos con confirmación cuando impliquen riesgo;
- trabaje como sistema multiagente y multimotor, eligiendo el especialista y el
  modelo adecuados para cada tarea;
- mantenga contexto, historial, memoria y trazabilidad;
- cuide los recursos de la computadora y del teléfono;
- priorice privacidad: sensores, ubicación, archivos y mensajes deben ser
  opt-in, visibles y revocables.

## Asistente personal para compras y recetas

Este es un objetivo funcional explícito del proyecto, además del análisis de
fotos. ADA debería poder ayudar a planificar y resolver compras cotidianas sin
convertirse en una aplicación de supermercado específica.

### Objetivo

ADA debe poder mantener una lista de compras, entender qué hace falta en la
casa, sugerir recetas y aprovechar señales de contexto para recordar una compra
en el momento adecuado. Por ejemplo, si el usuario entra a una zona autorizada
del supermercado, ADA podría avisar que hay una lista pendiente o mostrar una
receta compatible con los ingredientes disponibles.

### Lo que existe hoy

- La arquitectura conversacional puede recibir una lista o una solicitud de
  receta como texto.
- La memoria persistente puede servir como base para guardar preferencias y
  procedimientos.
- El diseño previsto de eventos permite incorporar ubicación, horarios y
  notificaciones.

No existe todavía un módulo de compras, inventario, recetas ni integración con
un supermercado. ADA tampoco detecta actualmente que el usuario está en el
supermercado.

### Lo que falta construir

- Lista de compras persistente con cantidades, unidades, categorías y prioridad.
- Estados de producto: pendiente, comprado, reemplazado, pospuesto o cancelado.
- Inventario doméstico opcional con fecha de vencimiento y nivel estimado.
- Recetario con ingredientes, porciones, tiempo, dificultad y restricciones.
- Generación de recetas según lo que hay disponible y lo que se desea comprar.
- Plan semanal de comidas y consolidación automática de ingredientes repetidos.
- Conversión de una receta en lista de supermercado.
- Registro de precios o presupuesto, si el usuario decide incorporarlos.
- Notificaciones por horario, evento o entrada a una zona.
- Integración móvil mediante Tasker como primer prototipo de geofencing.
- Confirmación antes de agregar compras, compartir datos o ejecutar acciones.

### Flujo esperado de compras

```text
Preferencia, receta o necesidad
        ↓
Lista de compras persistente
        ↓
Planificación y agrupación por categoría
        ↓
Evento: horario, ubicación o mensaje
        ↓
Recordatorio contextual
        ↓
Confirmación y actualización de la lista
```

Ejemplos de mensajes que ADA debería entender:

```text
Agregá leche, tomates y arroz a la lista.
¿Qué puedo cocinar con pollo, papas y cebolla?
Armame una lista para hacer tacos para cuatro personas.
Planificá cinco cenas económicas para esta semana.
Avisame cuando esté cerca del supermercado si todavía falta comprar leche.
Ya compré los tomates; marcálos como comprados.
```

### Privacidad y límites

La ubicación debe ser opcional y preferentemente procesada en el teléfono. El
evento mínimo debería ser `entered_zone(supermercado)`, sin enviar el recorrido
completo. ADA debe permitir definir zonas, horarios, frecuencia, retención y
desactivación de notificaciones. Las compras, pagos o pedidos online quedan
fuera del alcance inicial y siempre requerirían confirmación explícita.

La autonomía debe significar iniciativa controlada, no actividad permanente sin
límites. ADA tiene que saber cuándo observar, cuándo esperar, cuándo preguntar
y cuándo actuar.

## Lo que ya existe

### Núcleo de ADA

- Agente local con parser de intenciones y routing de skills.
- Memoria persistente SQLite para conversaciones, tareas y procedimientos.
- Interfaz web local con historial de conversación.
- Runtime local administrado para Ollama.
- Arquitectura preparada para más de un motor, aunque la configuración actual
  prioriza Ollama.
- Confirmación para operaciones riesgosas sobre archivos y sistemas.

### Sistema multiagente

- `TechnicalPhotoAgent` para mediciones técnicas.
- `ContextPhotoAgent` para sujeto, evento, estilo y sesión.
- `PhotoReviewAgent` para recomendación y selección.
- `MultiAgentCoordinator` para combinar especialistas.
- Workflow único para una foto individual y para cada archivo de un lote.

### Fotografía

- Lectura de JPG y RAW mediante Pillow y rawpy.
- Evaluación de enfoque, exposición, clipping, contraste, ISO, ruido y
  composición técnica.
- Análisis visual con modelo especializado.
- Tolerancia diferenciada para RAW y JPG.
- Identificación probabilística del contexto y coincidencia con la sesión.
- Selección de lotes sin cupo fijo de fotos buenas.
- Generación de XMP archivo por archivo para Lightroom.
- Rating, estado, motivo y flags `xmpDM:good` en los sidecars.
- Detección conservadora de ráfagas usando metadatos disponibles, tiempo y
  similitud visual.

### Operación y estabilidad

- Procesamiento fotográfico limitado por defecto a un archivo a la vez.
- Coordinación con un hilo y Ollama con dos hilos solicitados.
- Pausa de admisión cuando la carga del sistema es alta.
- Pruebas automatizadas para análisis, selección y XMP.
- Documentación técnica en esta carpeta.

## Lo que falta para el objetivo

### 1. Autonomía basada en eventos

ADA todavía depende principalmente de que alguien le escriba. Falta un
subsistema de eventos que pueda detectar, con permisos explícitos:

- llegada de nuevas fotos a una carpeta;
- finalización de una copia o importación;
- aparición de una carpeta de evento nueva;
- cambios en un directorio observado;
- horarios o tareas programadas;
- mensajes o comandos recibidos desde un canal externo;
- señales del teléfono, como entrada a una zona autorizada.

El watcher no debe lanzar directamente cualquier acción. Debe crear un evento,
evaluar reglas, consultar el contexto y generar una tarea auditable.

Flujo esperado:

```text
Señal autorizada → Evento → Regla → Plan → Confirmación o ejecución → Registro
```

### 2. Scheduler y sistema de tareas

Falta un scheduler persistente con:

- tareas únicas, recurrentes y disparadas por eventos;
- reintentos con backoff;
- prioridad y vencimiento;
- bloqueo para evitar dos análisis simultáneos del mismo lote;
- pausa global y cancelación;
- estado visible: pendiente, ejecutando, pausada, completada o fallida;
- límites de CPU, memoria, disco y concurrencia por tarea.

Un cron que solamente envía prompts sería un primer prototipo, pero la solución
final debe tener tareas estructuradas y no depender de texto libre.

### 3. Agente móvil

Para ubicación, sensores y notificaciones se necesita un componente móvil. Hay
dos caminos:

- prototipo rápido con Tasker, que ya resuelve geofencing, sensores y envío de
  webhooks con bajo consumo;
- aplicación propia con React Native o Capacitor, si se necesita una
  experiencia integrada y control completo.

La app móvil debe enviar eventos mínimos, no transmitir ubicación continuamente.
Ejemplo: `entered_zone(supermercado)` en lugar de subir el recorrido completo.
Debe existir consentimiento por sensor, indicador de actividad, frecuencia
configurable y botón de revocación.

### 4. Integraciones de mensajería

Telegram es el canal más simple para el primer adaptador porque tiene bot API y
permite recibir mensajes, imágenes y comandos. WhatsApp debe evaluarse después,
considerando costos, políticas y límites de la API oficial.

El adaptador no debe contener lógica de negocio. Debe traducir:

```text
mensaje externo → evento de entrada → ADA → respuesta y acciones auditadas
```

### 5. Despliegue autónomo

La computadora de recambio puede funcionar como nodo ADA permanente. La primera
opción debe ser una distribución Linux estable y simple de mantener, por
ejemplo Ubuntu LTS o Linux Mint. La decisión final debe basarse en:

- compatibilidad con GPU y aceleración disponible;
- consumo en reposo;
- facilidad de actualizaciones;
- soporte de Ollama;
- copias de seguridad;
- acceso remoto seguro.

El despliegue debería incluir servicios separados para API, scheduler, watcher,
Ollama y base de datos, administrados por systemd o Docker Compose. No conviene
que un único proceso monolítico sea responsable de todo.

## Mejoras prioritarias

### Prioridad 1: autonomía segura

1. Crear `event_bus` y esquema de eventos persistentes.
2. Crear scheduler con tareas, reintentos y cancelación.
3. Implementar watcher de carpetas para detectar nuevas fotos.
4. Agregar modo simulación: ADA propone qué haría sin ejecutarlo.
5. Agregar registro de auditoría con causa, regla, agente, motor y resultado.

### Prioridad 2: fotografía de producción

1. Procesar lotes en segundo plano con progreso visible.
2. Mantener límites de CPU, memoria y concurrencia por configuración.
3. Agregar ExifTool opcional para MakerNotes y ráfagas de Sony/Nikon.
4. Comparar ráfagas y duplicados con embeddings o hashes perceptuales.
5. Permitir calibración por cámara a partir de selecciones confirmadas por el
   fotógrafo.
6. Generar reportes resumidos además de los XMP.

### Prioridad 3: acceso móvil

1. Implementar bot de Telegram como adaptador de eventos.
2. Probar Tasker como prototipo de ubicación y automatización.
3. Definir permisos, zonas, frecuencia y retención de datos.
4. Recién después evaluar una app propia con Capacitor o React Native.

### Prioridad 4: compras y recetas

1. Crear skills `shopping_list`, `inventory` y `recipes` con almacenamiento
   estructurado.
2. Implementar comandos de alta, baja, edición y marcado de compras.
3. Permitir generar recetas y listas a partir de ingredientes disponibles.
4. Agregar preferencias alimentarias, presupuesto y cantidad de comensales.
5. Integrar recordatorios locales por horario.
6. Probar geofencing con Tasker sin enviar ubicación continua.
7. Recién después evaluar precios, supermercados y pedidos externos.

### Prioridad 5: nodo Linux permanente

1. Preparar instalación reproducible.
2. Separar servicios y configurar reinicio automático.
3. Agregar health checks, logs rotativos y backups.
4. Configurar acceso remoto seguro sin exponer Ollama directamente a internet.

## Principios que deben guiar cada desarrollo

- Local-first: usar el motor local cuando sea suficiente.
- Privacy-by-design: pedir solo los datos necesarios.
- Event-driven: la autonomía nace de eventos y reglas, no de prompts ocultos.
- Human-in-the-loop: confirmar acciones irreversibles o ambiguas.
- Resource-aware: preferir tardar más antes que bloquear la computadora.
- Modularidad: canales, sensores, agentes, motores y skills deben poder cambiarse
  de manera independiente.
- Observable: toda acción autónoma debe explicar por qué ocurrió.
- Reversible: las acciones deben poder pausarse, cancelarse o deshacerse cuando
  sea posible.

## Qué no debería hacerse todavía

- Enviar ubicación permanente al servidor.
- Exponer Ollama o la API de ADA directamente a internet.
- Crear una app móvil completa antes de validar los eventos con Tasker.
- Ejecutar acciones de archivos sin confirmación y auditoría.
- Aumentar workers para acelerar lotes si se supera el presupuesto de recursos.
- Agregar otro modelo sin definir qué especialista lo usa y cómo se evalúa.

## Definición de éxito

El proyecto avanza en la dirección correcta cuando ADA puede:

1. detectar que llegaron nuevas fotos;
2. crear una tarea de análisis sin prompt manual;
3. procesar el lote respetando el límite de recursos;
4. generar XMP y un resumen entendible;
5. pedir confirmación antes de mover o borrar;
6. recordar la decisión del usuario para mejorar futuras selecciones;
7. explicar qué evento disparó la tarea y qué agente tomó cada decisión.
