# Documentación del proyecto

Esta carpeta describe ADA como sistema: su objetivo, arquitectura, funciones,
integraciones y operación. No contiene la documentación específica de cada
capability; esa información está en [`../skills/README.md`](../skills/README.md).

## Índice

- [Objetivo y roadmap](roadmap.md)
- [Arquitectura](architecture/overview.md)
- [Estructura de carpetas](architecture/folder-structure.md)
- [Análisis de fotos](features/photo-analysis.md)
- [Compras y recetas](features/shopping-and-recipes.md)
- [XMP y ráfagas](features/xmp-and-bursts.md)
- [Telegram y Ollama](integrations/telegram-and-ollama.md)
- [Operación y recursos](operations.md)

## Regla de organización

Si un documento explica una capacidad del producto, una decisión de
arquitectura, una integración, una prioridad o cómo ejecutar ADA, pertenece a
`project/`. Si explica los parámetros, entradas, salidas y permisos de una
función ejecutable concreta, pertenece a `src/ada/capabilities/`.
