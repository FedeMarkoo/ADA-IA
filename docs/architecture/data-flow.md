# Flujo de una petición

Una solicitud entra desde la web o Telegram, se clasifica, se valida y se resuelve con un modelo o una herramienta MCP. El resultado y la traza se guardan localmente antes de volver al canal de origen.

```mermaid
flowchart TD
    Input[Mensaje web o Telegram] --> Endpoint[/api/chat o /api/chat/stream/]
    Endpoint --> Session[Sesión y contexto]
    Session --> Router[Intent Router]
    Router --> Decision{Tipo de tarea}
    Decision -->|Conversación| Model[Model Manager]
    Decision -->|Herramienta| Policy[Policy Engine]
    Policy --> Check{¿Permitida?}
    Check -->|Sí| MCP[MCP Manager]
    Check -->|No o requiere confirmación| Request[Solicitar confirmación o informar bloqueo]
    MCP --> Tool[Servidor MCP]
    Tool --> Result[Resultado estructurado]
    Model --> Result
    Result --> Memory[(Memoria y auditoría SQLite)]
    Memory --> Response[Respuesta formateada]
    Response --> Output[Web JSON/SSE o Telegram]
```

## Reglas de seguridad

| Tipo de acción | Tratamiento |
|---|---|
| Lectura de datos permitidos | Puede ejecutarse automáticamente |
| Escritura de archivos o comandos | Respeta `allowed_roots`, allowlist y `confirm_risky` |
| Mutación desde la web | Requiere host local, JSON y token CSRF si hay sesión |
| Evento externo | Requiere `X-ADA-Event-Token` |

## Respuesta en streaming

El endpoint `/api/chat/stream` publica fases de ejecución y fragmentos de respuesta mediante Server-Sent Events. El detalle de esos eventos y las secuencias de seguridad está en [Flujos técnicos completos](complete-flows.md).
