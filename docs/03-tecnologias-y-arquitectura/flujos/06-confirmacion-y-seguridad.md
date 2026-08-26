# 3.8.6 Confirmación y seguridad

Las lecturas siguen el flujo normal. Las mutaciones generan una vista previa y solo se ejecutan cuando la llamada contiene confirmación válida; además se aplican allowlists de rutas/comandos y validación en el punto de ejecución.

## Qué ocurre

Una acción mutante se detiene antes de producir efectos. La capa de chat conserva la acción pendiente y muestra la vista previa; al confirmar, vuelve a enviar la operación con la marca de confirmación. `MCPManager` comprueba esa marca independientemente de que la llamada venga del router, del chat o de una invocación directa. En paralelo, la política valida rutas contra `allowed_roots`, comandos contra su allowlist y límites de lectura.

## Implementación

- Autorización: [`PolicyEngine.authorize`](../../../ada/domain/policy.py#L78) y [`PolicyEngine.requires_confirmation`](../../../ada/domain/policy.py#L54).
- Confirmación en tools: [`MCPManager.execute_tool`](../../../ada/mcps/manager.py#L610).
- Confirmar/cancelar por HTTP: [`confirm_action`](../../../ada/interfaces/web/routes/chat.py#L41) y [`cancel_action`](../../../ada/interfaces/web/routes/chat.py#L60).
- Estado pendiente: [`WebSessionState`](../../../ada/interfaces/web/state.py#L77).
- Tools mutantes: [`mcps/filesystem/server.py`](../../../mcps/filesystem/server.py#L70).
