# 3.3 Componentes principales

| Componente | Responsabilidad |
|---|---|
| `Agent` | Coordina decisión, ejecución y respuesta |
| `IntentRouter` | Produce acción y señales de routing |
| `ModelManager` | Selecciona y llama proveedores/modelos |
| `ContextManager` | Construye contexto acotado |
| `MCPManager` | Descubre, valida y ejecuta tools |
| `Memory` | Persistencia SQLite y búsqueda |
| `MemoryRefiner` | Refinamiento y compactación periódica |
