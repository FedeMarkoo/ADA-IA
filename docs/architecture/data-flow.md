# Flujo de Datos y Razonamiento

Este documento detalla el ciclo de vida de una consulta desde que ingresa al sistema hasta que se genera una respuesta o se ejecuta una herramienta.

---

## 🔄 Ciclo de Vida de una Petición

```text
1. Usuario envía mensaje (vía Web Dashboard o Telegram)
   │
   ▼
2. Endpoint `/api/chat` o `/api/chat/stream`
   │
   ▼
3. IntentRouter (ada.application.router)
   ├── Clasificación determinística / semántica rápida
   └── Detección de intenciones (chat, photo, food, files, system, etc.)
   │
   ▼
4. PolicyEngine (ada.domain.policy)
   ├── Verificación de seguridad y confirmaciones requeridas
   └── Validación de rutas autorizadas (allowed_roots)
   │
   ▼
5. Planner / MCP Execution / MultiAgentCoordinator
   ├── Invocación a herramientas MCP (`mcps/`)
   └── Consulta a modelos LLM locales (OllamaClient)
   │
   ▼
6. Persistencia y Memoria (ada.infrastructure.persistence.sqlite)
   ├── Registro de tarea y auditoría en `ada/memory.db`
   └── Actualización de contexto conversacional
   │
   ▼
7. Respuesta formateada devuelta al cliente
```

---

## 🛡️ Políticas de Confirmación y Riesgo

Para garantizar la seguridad de los datos personales:
- Las lecturas (`filesystem.list_files`, `food.recipes`, `photography.analyze_photo`) tienen riesgo **`safe`** y se ejecutan automáticamente.
- Las mutaciones de archivos (`filesystem.write_file`, `filesystem.move_files`, `system.run_command`) tienen riesgo **`confirmation`** y requieren autorización previa si `confirm_risky` está habilitado.
