# Mejora MEM-01 — Compactador de memoria conversacional

## Objetivo

Evitar que las conversaciones largas crezcan indefinidamente en SQLite y en el contexto que ADA carga para responder. El compactador conserva un resumen local acotado y deja intactos los mensajes recientes necesarios para continuar el hilo.

## Diseño

- Se ejecuta dentro del ciclo periódico de `MemoryRefiner`.
- Solo procesa sesiones que superan `memory_compaction_threshold_messages`.
- Genera un resumen extractivo, independiente de modelos y proveedores; no envía historial privado a LiteLLM, Ollama ni servicios externos.
- Conserva los últimos `memory_compaction_keep_messages` mensajes.
- Guarda el resumen en `conversation_summaries` y elimina únicamente los mensajes anteriores en una transacción SQLite.
- El resumen queda limitado por `memory_compaction_max_summary_chars`.
- Si falla una sesión, se registra el warning y el refinador continúa con las demás.

## Configuración

```json
{
  "memory_compaction_enabled": true,
  "memory_compaction_threshold_messages": 100,
  "memory_compaction_keep_messages": 40,
  "memory_compaction_max_summary_chars": 6000
}
```

Para desactivarlo temporalmente usar `memory_compaction_enabled: false`. La compactación es conservadora: no borra la ventana reciente ni las memorias semánticas, de perfil o procedimientos.

## Checklist

- [x] Compactación periódica integrada al `MemoryRefiner`.
- [x] Resumen local con límite de tamaño.
- [x] Retención configurable de mensajes recientes.
- [x] Operación transaccional y compatible con el cifrado existente.
- [x] Test de compactación y retención.
