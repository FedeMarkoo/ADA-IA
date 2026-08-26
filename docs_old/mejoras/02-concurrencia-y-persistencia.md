# ⚡ 02. Concurrencia y Persistencia

## Estado de Implementación

| ID | Mejora / Corrección | Estado | Commit |
|---|---|---|---|
| CON-01 | Aislamiento de sesiones web y pending actions mediante cookies persistentes | ✅ Implementado | `4db33d3` |
| CON-02 | SQLite WAL mode (`PRAGMA journal_mode=WAL`) y sincronización NORMAL | ✅ Implementado | `4db33d3` |
| CON-03 | Thread-safety con `threading.RLock()` en `Memory` y `SecureVault` | ✅ Implementado | `4db33d3` |
| CON-04 | Prevención de deadlocks entre `MemoryRefiner` y `Memory` | ✅ Implementado | `4db33d3` |

---

## Detalle de Implementaciones

### CON-01: Estado Aislado por Sesión
- En lugar de mantener variables mutables globales para `conversation` y `pending_action`, cada pestaña de navegador o usuario de Telegram posee una instancia de `WebSessionState` aislada y respaldada en SQLite.
- Evita que la confirmación de una acción sensible en una pestaña ejecute por error la acción de otra sesión concurrente.

### CON-02 & CON-03: Concurrencia en SQLite
- Activación de Write-Ahead Logging (WAL), permitiendo múltiples lectores concurrentes mientras se produce una escritura.
- Todas las mutaciones en `Memory`, `SecureVault` y `DebugLog` están serializadas con cerrojos reentrantes (`threading.RLock`).
