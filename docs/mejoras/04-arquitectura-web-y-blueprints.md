# 🏗️ 04. Arquitectura Web y Blueprints

## Estado de Implementación

| ID | Mejora / Corrección | Estado | Commit |
|---|---|---|---|
| ARQ-01 | División de `server.py` (>2,100 líneas) en Flask Blueprints modulares | ✅ Implementado | `En este branch` |
| ARQ-02 | Separación clara de responsabilidades: Core, Chat, Models, Vault, Healthcheck y System | ✅ Implementado | `En este branch` |
| ARQ-03 | Soporte dual de servidores: WSGI (Flask) y ASGI (FastAPI/Uvicorn) | ✅ Implementado | `a5a3599` |

---

## Estructura de Blueprints en `ada/interfaces/web/routes/`

```text
ada/interfaces/web/
├── server.py               # Application Factory e inicializador central
├── asgi.py                 # Factory para servidor ASGI alternativo
├── doctor.py               # Diagnóstico y auto-sanación de servicios
└── routes/
    ├── __init__.py         # Registro central de blueprints
    ├── core.py             # Rutas base (/), estado general, métricas y CSRF
    ├── chat.py             # Endpoints de chat síncrono, SSE y acciones pendientes
    ├── models.py           # Catálogo, políticas, Ollama y suites de benchmark
    ├── vault.py            # Bóveda de credenciales cifradas y rate-limiting
    ├── health.py           # Healthcheck de capacidades y checklist funcional
    └── system.py           # Triggers, Telegram status, presencia y updates
```
