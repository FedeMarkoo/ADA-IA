# Documentación de ADA-IA

ADA-IA es un asistente local con modelos de lenguaje, herramientas MCP, dashboard, automatizaciones y canales externos. Esta página es el punto de entrada: elegí el recorrido según lo que necesites hacer.

## Empezar a usar ADA

1. [Instalación e inicio](guides/getting-started.md): preparar el entorno y abrir ADA.
2. [Guía de uso del dashboard](user-guide.md): operar cada pantalla con capturas reales.
3. [Aplicación de escritorio](desktop.md): requisitos y ejecución del shell GTK/WebKit.
4. [Operaciones y diagnóstico](guides/operations.md): salud, métricas, backups y alertas.

## Usar y configurar capacidades

- [Dashboard y API](dashboard/README.md): alcance del panel, navegación y accesos rápidos.
- [Herramientas MCP](mcps/README.md): registro, protocolo y herramientas disponibles.
- [Modelos y benchmarks](models/README.md): catálogo, roles y mediciones.
- [Telegram](telegram/README.md): bot, configuración y ejecución.
- [Catálogo funcional y API](functional-catalog.md): referencia de capacidades y endpoints.

## Entender la implementación

- [Arquitectura](architecture/overview.md): componentes y responsabilidades.
- [Flujo de una petición](architecture/data-flow.md): router, seguridad, modelos, MCPs y memoria.
- [Estructura del proyecto](architecture/folder-structure.md): módulos y límites.
- [Flujos técnicos completos](architecture/complete-flows.md): secuencias, seguridad y SSE.
- [Routing multiproveedor](architecture/llm-routing-and-omnirouter.md): política de proveedores y OmniRoute.

## Mantenimiento y decisiones

- [Desarrollo y tests](guides/development.md)
- [Actualizaciones seguras](AUTO_UPDATE_AND_SERVICE_RESTART.md)
- [Memoria y contexto compartido](SHARED_CONTEXT_MEMORY.md)
- [Roadmap y mejoras](mejoras.md)
- [Changelog](CHANGELOG.md)

## Capturas

La [galería de capturas](screenshots/README.md) reúne las 12 vistas del dashboard. Las mismas imágenes aparecen contextualizadas dentro de la [guía de uso](user-guide.md), no hace falta revisar la galería para seguir el recorrido normal.
