# Guía de Desarrollo y Testing

Guía para desarrolladores que deseen extender o modificar ADA-IA.


## Ejecución de tests automatizados

La suite de pruebas utiliza **`pytest`** y cubre el 100% de los subsistemas (fotografía, router, memoria SQLite, integración con Ollama, MCPs y Telegram):

```bash
# Ejecutar toda la suite de tests
pytest

# Ejecutar con output detallado
pytest -v

# Ejecutar una prueba específica
pytest tests/test_photo_analysis.py
```


## Estándar de empaquetado

- El proyecto sigue el estándar de **Namespace Packages de Python moderno (PEP 420)**. No se utilizan archivos `__init__.py`.
- Todas las dependencias y configuración del empaquetado se encuentran centralizadas en `pyproject.toml`.


## Agregar un nuevo servidor MCP

1. Creá una subcarpeta en `mcps/<tu_mcp>/`.
2. Implementá tu servidor heredando de `mcps.protocol.StdioMCPServer`.
3. Registrá tu servidor en `mcps/config.json` dentro de `mcpServers`.
4. El `MCPManager` de ADA lo descubrirá automáticamente y lo expondrá en el Dashboard.
