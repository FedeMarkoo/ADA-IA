# Multi-agent architecture

ADA separa el enrutamiento, la ejecución y la evaluación fotográfica. Esto
permite cambiar el motor de lenguaje o agregar especialistas sin reescribir la
interfaz.

## Flujo general

1. La interfaz web o la CLI recibe el mensaje.
2. `agent_loop.py` identifica la intención y extrae rutas, carpeta y opciones.
3. `Agent.decide_and_run()` elige una skill o un motor generativo.
4. Las skills ejecutan operaciones acotadas y devuelven resultados estructurados.
5. La conversación persistente guarda el mensaje y la respuesta.

## Workflow fotográfico

`MultiAgentCoordinator` ejecuta los especialistas registrados en `AgentRegistry`:

- `TechnicalPhotoAgent`: RAW/JPG, enfoque, exposición, ruido, contraste y
  composición técnica.
- `ContextPhotoAgent`: sujeto, evento, estilo y coincidencia con la sesión.
- `PhotoReviewAgent`: criterio de selección, rating de Lightroom, fortalezas,
  problemas y recomendación.

Los agentes técnicos y de contexto pueden ejecutarse en paralelo. El coordinador
combina sus resultados y conserva campos compatibles con respuestas anteriores.
La misma función `analyze_photo()` es usada para una imagen individual y para
cada elemento de un lote.

## Motores

El `ModelManager` abstrae el proveedor. El análisis técnico puede funcionar sin
modelo. El análisis semántico RAW necesita un modelo con visión, actualmente
configurado como `qwen2.5vl:3b` sobre Ollama. La interfaz permite incorporar
otros motores sin acoplar los agentes a Ollama.

## Memoria y seguridad

La memoria SQLite registra conversación, tareas, conocimiento y procedimientos.
Las skills de lectura no modifican archivos. Las operaciones potencialmente
destructivas requieren confirmación cuando `confirm_risky` está activo.
