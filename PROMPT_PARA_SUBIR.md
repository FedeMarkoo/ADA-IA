# Prompt para subir la capa RAG de ADA

Necesito que incorpores esta implementación al repositorio público
`FedeMarkoo/ADA-IA`.

## Objetivo

Agregar una capa RAG a ADA como un componente de contexto independiente,
integrado junto a `tools` y `memories`, respetando la arquitectura hexagonal del
proyecto. La primera implementación usa SQLite FTS5 para mantener el enfoque
local-first y evitar agregar un servicio externo de vectores en esta etapa.

## Contenido de este paquete

El paquete contiene los archivos modificados y nuevos de la implementación,
manteniendo su estructura relativa al repositorio:

- Puerto `RagDocumentStore`.
- Adaptador `SqliteRagDocumentStore` basado en SQLite FTS5.
- `RagManager` para indexar y recuperar documentos.
- `RagContextItem` como nueva capa de contexto.
- Configuración `ada.rag.*`.
- Esquema SQLite, tabla FTS5 y triggers de sincronización.
- Endpoint `POST /api/v1/rag/documents` para indexar documentos.
- Tests unitarios.
- ADR-003 y actualización de la documentación de arquitectura.

## Instrucciones de trabajo

1. Trabajá sobre la rama actualizada `main` del repositorio
   `FedeMarkoo/ADA-IA`.
2. Creá una rama equivalente a `codex/add-local-rag`.
3. Copiá los archivos de este paquete respetando sus rutas. No sobrescribas
   cambios ajenos que hayan aparecido en `main` desde la creación del paquete:
   integrá manualmente los conflictos.
4. Revisá la implementación completa antes de abrir el PR. En particular,
   verificá que:
   - `RagDocumentStore` sea un puerto de application.
   - SQLite y JDBC queden solamente en infrastructure/out.
   - La búsqueda filtre siempre por `conversationId`.
   - La consulta FTS5 no permita inyección de sintaxis MATCH.
   - El contexto tenga límites de cantidad y caracteres.
   - El contenido recuperado se identifique por fuente y se trate como
     conocimiento auxiliar, no como instrucciones confiables.
   - Los DTOs REST estén en `infrastructure.in.rest.dto`.
   - No se incluyan secretos, bases SQLite, logs, builds ni rutas locales.
5. Ejecutá todos los checks del proyecto:

   ```bash
   mvn --batch-mode --no-transfer-progress -DskipTests \
     -f libs/ada-observability/pom.xml install
   mvn --batch-mode --no-transfer-progress verify
   ```

6. Si algún check falla, corregí el problema, agregá o ajustá tests cuando
   corresponda y volvé a ejecutar toda la validación.
7. Abrí un Pull Request contra `main` con una descripción que incluya:
   - qué se implementó;
   - por qué se eligió SQLite FTS5 como primera estrategia;
   - limitaciones actuales: no hay embeddings ni chunking automático;
   - resultados de `mvn verify`;
   - riesgos y próximos pasos.
8. Esperá y revisá todos los checks de CI, la revisión de CodeRabbit y la
   revisión humana. Respondé los comentarios y corregí lo necesario.
9. Mergeá a `main` únicamente cuando todos los checks estén verdes y las
   revisiones requeridas estén aprobadas. No hagas push directo a `main`.

## Decisión técnica

SQLite FTS5 se eligió porque ADA ya usa SQLite, permite recuperar texto de
forma local y determinista, y evita introducir infraestructura adicional. El
puerto `RagDocumentStore` deja abierta una futura implementación híbrida o
vectorial con embeddings sin modificar `ChatUseCase` ni el contrato del
contexto.

## API de indexación

`POST /api/v1/rag/documents`

```json
{
  "conversationId": "default",
  "source": "manual.md",
  "content": "Contenido que ADA podrá recuperar como conocimiento."
}
```

La recuperación ocurre automáticamente durante la creación del contexto de
una conversación cuando `ADA_RAG_ENABLED` está habilitado.

## Estado de origen

La implementación inicial fue preparada en la rama `codex/add-local-rag`,
commit `a54d33c`. Ese commit sirve como referencia, pero el PR debe partir del
`main` vigente y pasar nuevamente todos los checks.
