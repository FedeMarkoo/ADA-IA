# ADR-003: RAG local-first con SQLite FTS5

## Estado

Aceptado.

## Decisión

ADA incorpora una capa RAG detrás del puerto `RagDocumentStore`. La primera
implementación persiste documentos en SQLite y los recupera con FTS5, filtrando
por `conversationId` y limitando la cantidad y el tamaño del contexto.

## Motivo

SQLite ya es una dependencia operativa de ADA y FTS5 permite una búsqueda local,
determinista y sin incorporar un servicio vectorial ni una API externa. El puerto
permite reemplazar o complementar la recuperación lexical con embeddings cuando
la evaluación de calidad lo justifique.

## Límites

Esta versión no genera embeddings ni hace chunking automático: el consumidor
indexa unidades documentales razonables. El contenido recuperado se presenta al
modelo como conocimiento auxiliar que debe verificarse contra la fuente.
