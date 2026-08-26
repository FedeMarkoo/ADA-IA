# 10. Seguridad fail-closed y defensa en profundidad

## Objetivo

Evitar que una configuración ausente o vacía habilite acceso al disco, al bot de Telegram o a acciones sensibles. En ADA, los defaults de seguridad deben denegar hasta que exista una autorización explícita.

## Estado de implementación

| ID | Mejora / Corrección | Estado | Prioridad |
|---|---|---|---|
| SEC-08 | `allowed_roots` vacío debe denegar todo | 🔴 Pendiente | Crítica |
| SEC-09 | Propagar `allowed_roots` al MCP filesystem | 🔴 Pendiente | Crítica |
| SEC-10 | `allowed_chat_ids` vacío debe bloquear Telegram | 🔴 Pendiente | Crítica |
| SEC-11 | Aplicar `requires_confirmation` dentro de `execute_tool()` | 🔴 Pendiente | Alta |
| SEC-12 | Reemplazar `except Exception: pass` por logging y errores explícitos | 🟠 Pendiente | Alta |
| SEC-13 | Limitar tamaño de `read_file` y revisar permisos de secretos en Windows | 🟡 Pendiente | Media |
| SEC-14 | Usar `--` en argumentos del Git MCP | 🟡 Pendiente | Media |

## Principios

- Lista de raíces vacía = ninguna ruta autorizada; nunca “todo el disco”.
- Lista de chats vacía = ningún usuario autorizado.
- El router puede proponer una acción, pero la capa de ejecución debe volver a validar autorización, parámetros y confirmación.
- Los fallos de configuración, credenciales y herramientas deben ser visibles en logs y healthchecks.

## Riesgos actuales

1. `allowed_roots: []` puede hacer que la política de rutas acepte cualquier path y `validate_config` no advierta el problema.
2. El MCP de filesystem se instancia sin los directorios permitidos y no respeta la política configurada.
3. Telegram queda abierto si `allowed_chat_ids` está vacío.
4. `execute_tool()` confía en las capas superiores para filtrar herramientas que requieren confirmación.
5. Varios `except Exception: pass` ocultan MCPs mal configurados, escrituras fallidas y errores de SecureVault.
6. `read_file` y recorridos recursivos no tienen límites suficientes frente a árboles o archivos grandes.

## Criterios de aceptación

- Tests explícitos para listas vacías, paths fuera de allowlist, chat IDs desconocidos y ejecución directa de tools sensibles.
- Ninguna mutación sensible se ejecuta sin confirmación válida, incluso si se invoca fuera del router.
- Todo error recuperable queda registrado con contexto; los errores de configuración aparecen en diagnóstico.
