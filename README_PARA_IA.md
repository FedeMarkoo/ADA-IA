# Instrucciones para subir este cambio a ADA-IA

## Objetivo

Este paquete contiene la implementación de una capa de optimización de prompts para `FedeMarkoo/ADA-IA`, inspirada en Caveman Compression.

La capa conserva el request completo dentro de Ada y genera una copia optimizada únicamente antes de enviarla al proveedor LLM. Por seguridad, solo compacta bloques generados por Ada de tipo `MEMORIES` y `COMPACTED_PROMPT`.

No debe modificar el prompt del usuario, el system prompt principal, JSON, código, schemas de herramientas, tool calls ni respuestas de herramientas.

## Pasos para otra IA

1. Clonar o abrir el repositorio correcto:

   `https://github.com/FedeMarkoo/ADA-IA.git`

2. Confirmar que la rama base sea `main` y que no haya cambios ajenos pendientes.

3. Copiar el contenido de este paquete sobre el checkout del repositorio, conservando la estructura de carpetas.

4. Crear una rama separada:

   `git switch -c codex/prompt-optimization`

5. Revisar los cambios y ejecutar:

   `mvn verify`

6. Si los tests y el formateo pasan, crear un commit coherente:

   `git add .`

   `git commit -m "feat: optimize generated prompts before provider calls"`

7. Publicar la rama:

   `git push -u origin codex/prompt-optimization`

8. Abrir un Pull Request contra `main` con un título similar a:

   `feat: optimize generated prompts before provider calls`

## Descripción sugerida para el PR

### Qué cambia

- Agrega el puerto `PromptOptimizer`.
- Agrega `CavemanPromptOptimizer`, una compresión local y determinística.
- Ejecuta la optimización en `LiteLlmClient`, justo antes de serializar el request para LiteLLM.
- Agrega configuración mediante `ADA_LLM_PROMPT_OPTIMIZATION_ENABLED` y `ADA_LLM_PROMPT_OPTIMIZATION_MIN_CHARS`.
- Agrega métricas de tokens estimados originales y optimizados.
- Agrega pruebas para compresión, preservación de contenido sensible y desactivación.

### Criterios de seguridad

- No registrar prompts ni datos personales.
- No hacer push directo a `main`.
- No mezclar este cambio con el PR del RAG.
- Esperar `mvn verify`, CodeRabbit y revisión humana antes de mergear.

## Estado conocido

La implementación local fue creada en dos commits:

- `f551b8e feat: optimize generated prompts before provider calls`
- `c5e7b16 test: cover prompt optimization safeguards`

El entorno original no tenía Maven ni Java 21, por lo que la validación completa debe ejecutarse en CI o en un entorno con Java 21.
