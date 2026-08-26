# 10. Seguridad fail-closed y defensa en profundidad

## Objetivo

Evitar que una configuración ausente o vacía habilite acceso al disco, al bot de Telegram o a acciones sensibles. Los tres problemas críticos comparten la misma causa de diseño: cuando falta configuración, ADA abre el acceso en lugar de cerrarlo.

Para un agente capaz de ejecutar acciones sobre la máquina, el default seguro debe ser **denegar hasta que exista una autorización explícita**.

## Estado de implementación

| ID | Mejora / Corrección | Estado | Prioridad |
|---|---|---|---|
| SEC-08 | `allowed_roots: []` debe denegar todo | ✅ Implementado | Crítica |
| SEC-09 | Propagar `allowed_roots` al MCP filesystem | ✅ Implementado | Crítica |
| SEC-10 | `allowed_chat_ids: []` debe bloquear Telegram | 🔴 Pendiente | Crítica |
| SEC-11 | Aplicar `requires_confirmation` dentro de `execute_tool()` | 🔴 Pendiente | Alta |
| SEC-12 | Reemplazar `except Exception: pass` por logging y errores explícitos | 🟠 Pendiente | Alta |
| SEC-13 | Limitar tamaño de `read_file` y revisar permisos de secretos en Windows | 🟡 Pendiente | Media |
| SEC-14 | Usar `--` en argumentos del Git MCP | 🟡 Pendiente | Media |

## SEC-08: `allowed_roots` debe ser fail-closed

### Problema

En `ada/domain/policy.py`, la lógica actual trata una lista vacía como ausencia de restricciones. Si `allowed_roots` queda en `[]`, la política de rutas devuelve `True` para cualquier path. Además, `validate_config` acepta esa configuración sin advertirlo.

El resultado es que una configuración incompleta puede habilitar todo el disco.

### Comportamiento esperado

```text
allowed_roots = []       → denegar cualquier path
allowed_roots = [A, B]   → permitir únicamente paths dentro de A o B
path fuera del allowlist → denegar
```

La validación de configuración debe distinguir entre un valor deliberadamente configurado y una configuración insegura. Para el modo local seguro, una lista vacía debe ser válida sintácticamente pero siempre denegatoria; opcionalmente puede producir un warning visible en healthcheck para facilitar el diagnóstico.

## SEC-09: el MCP filesystem debe respetar la política

### Problema

El MCP de filesystem se crea desde `manager.py` sin pasarle los directorios permitidos. En consecuencia, cae al `cwd` —el repositorio— y sus tools pueden leer o escribir dentro del código aunque la política del usuario indique otra cosa.

### Solución

El `MCPManager` debe recibir la configuración de raíces autorizadas y propagarla al servidor filesystem durante su creación y reinicio. La validación debe ocurrir también dentro de cada operación, no solamente al construir el servidor:

```text
config.allowed_roots
        ↓
MCPManager
        ↓
filesystem server / path policy
        ↓
read, write, list, group
```

No debe existir un fallback implícito al directorio actual para operaciones de usuario. Si no hay raíces autorizadas, las tools deben responder con una denegación clara.

## SEC-10: Telegram debe ser cerrado por defecto

### Problema

En `telegram/bot.py`, una lista vacía de `allowed_chat_ids` permite que cualquier persona que encuentre el bot le hable y potencialmente dispare acciones.

### Solución

```text
allowed_chat_ids = []       → ningún chat autorizado
chat_id no incluido          → rechazar y registrar
chat_id incluido             → continuar con el flujo normal
```

El rechazo no debe revelar secretos ni detalles internos. Los intentos deben quedar registrados con un identificador suficiente para auditar el evento.

## SEC-11: confirmación en el punto de ejecución

### Problema

`execute_tool()` no comprueba `requires_confirmation`; confía en que el router y las capas superiores ya hayan filtrado la acción. Una llamada directa como `execute_tool("filesystem.write_file", ...)` puede ejecutar una operación sensible sin confirmación.

### Solución

La confirmación debe ser una barrera obligatoria en la capa de ejecución:

```python
def execute_tool(name, params, confirmed=False):
    tool = registry.get(name)
    if tool is None:
        return None
    if tool.requires_confirmation and not confirmed:
        return {"pending": name, "reply": f"¿Confirmás {name}?"}
    validate_parameters(tool.parameters, params)
    return tool.handler(**params)
```

El router propone; el código valida la existencia de la tool, autorización, parámetros y confirmación. Ninguna capa anterior puede reemplazar esta defensa.

## SEC-12 a SEC-14: errores, límites y argumentos

- Los `except Exception: pass` deben convertirse en errores registrados con operación, componente y causa. Esto incluye configuración MCP malformada, tools que desaparecen del inventario, escrituras de configuración que fallan y `SecureVault.get()` cuando la clave maestra es incorrecta.
- `read_file` debe tener un límite explícito de bytes y un comportamiento definido para archivos grandes. Los `rglob("*")` deben evitar recorridos duplicados y contar con límites de profundidad/cantidad cuando corresponda.
- El Git MCP debe separar opciones de argumentos usando `--` para reducir el riesgo de inyección de argumentos:

```text
git <subcommand> -- <user-controlled-path>
```

- `chmod 0o600` no garantiza el mismo aislamiento en Windows, donde pueden prevalecer ACLs heredadas. La creación de secretos debe documentar la limitación y aplicar la protección nativa disponible; cualquier fallo no debe silenciarse.

## Criterios de aceptación

- Tests explícitos para `allowed_roots=[]`, paths fuera del allowlist, `allowed_chat_ids=[]`, chat IDs desconocidos y ejecución directa de tools sensibles.
- Ninguna mutación sensible se ejecuta sin confirmación válida, incluso si se invoca fuera del router.
- Un filesystem sin raíces autorizadas no puede caer al `cwd`.
- Todo error recuperable queda registrado con contexto; los errores de configuración aparecen en diagnóstico.
- Archivos y recorridos recursivos tienen límites verificables.
