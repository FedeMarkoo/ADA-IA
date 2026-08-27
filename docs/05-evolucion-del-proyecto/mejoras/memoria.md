# 5.2.4 Memoria

Memoria por capas, compactador local y MCP CRUD para agregar, consultar, modificar y eliminar recuerdos.

Diseño propuesto relacionado: [retrieval y reranking de memoria en el router](retrieval-reranking-de-memoria.md).

La modalidad `memory-as-a-tool` también está implementada: cuando el modelo principal necesita un recuerdo que no recibió en el contexto, puede solicitar `memory.search` una única vez. ADA limita la consulta a tres resultados, ejecuta solo esa tool y continúa la respuesta con el resultado; se puede desactivar con `memory_as_tool: false`.
