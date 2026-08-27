# 4.1 Métricas

Las métricas cubren latencia, errores, tokens, modelo seleccionado, llamadas MCP, memoria del proceso, CPU, GPU y estado de Ollama.

![Métricas de ADA](assets/metricas.png)
# Tokens por componente de contexto

ADA publica `ada_llm_tokens{component="system|memory|tools|prompt|response|total"}` para visualizar la composición de la última llamada al modelo. La definición, interpretación y consulta están en [Métricas de tokens por componente](../05-evolucion-del-proyecto/mejoras/metricas-de-tokens-por-componente.md).
