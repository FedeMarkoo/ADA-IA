# Dashboard ADA Hub

El dashboard es la interfaz local para operar ADA: muestra el estado del sistema, permite conversar con el agente, configurar modelos y herramientas, y administrar canales como Telegram.

## Acceso

Iniciá el servidor y abrí `http://127.0.0.1:5005`:

```bash
./.venv/bin/python -m ada.interfaces.web.server
```

La aplicación de escritorio carga esta misma interfaz dentro de una ventana nativa. Consultá [Aplicación de escritorio](../desktop.md) para sus requisitos.

## Recorrido de operación

| Objetivo | Pantalla | Qué permite hacer |
|---|---|---|
| Comprobar el sistema | Resumen | Consultar salud, recursos, modelos y servicios críticos |
| Entender una ejecución | Núcleo ADA | Ver canales, modelos, MCPs y traza de actividad |
| Probar una tarea | Conversar con ADA | Usar el chat con respuesta normal o streaming |
| Diagnosticar una falla | Healthcheck | Ejecutar casos, ver resultados y reintentar |
| Configurar el agente | Motor local, Modelos, Herramientas | Gestionar runtime, roles y MCPs |
| Gestionar canales | Disparadores y Telegram | Controlar eventos y el bot |

### Estado del sistema

![Resumen del dashboard](../screenshots/assets-overview.png)

### Herramientas MCP

![Herramientas MCP](../screenshots/assets-mcps.png)

### Conversación con ADA

![Chat de ADA](../screenshots/assets-chat.png)

## Documentación relacionada

- [Guía de uso completa](../user-guide.md): las 12 pantallas, acciones y capturas en orden de uso.
- [Referencia REST, SSE y catálogo](api-reference.md): contratos de la API, capacidades y servidores MCP.
- [Galería de capturas](../screenshots/README.md): consulta visual rápida de todas las vistas.
