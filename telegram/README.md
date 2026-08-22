# Servidor Independiente de Telegram Bot para ADA

Este módulo actúa como un **servidor y cliente de mensajería independiente** desacoplado del núcleo de ADA.

---

## 🚀 Ejecución administrada por ADA

1. Configurá tu token en la **Bóveda Cifrada (`vault.db`)**:
   - **Desde el Gestor Web**: Ingresá en `http://127.0.0.1:5005` → Pestaña **Telegram Bot** → **🔑 Configurar Token**.
   - **O por CLI**:
     ```bash
     .venv/bin/python -c "from utils.credentials import SecureVault; SecureVault().set('telegram_bot_token', 'TU_TOKEN_DE_BOTFATHER')"
     ```

2. En **Disparadores → Telegram**, seleccioná **Iniciar**. El gestor guarda el
   estado deseado, lanza el bot como proceso independiente y registra PID,
   salud y logs en `~/Desktop/ADA_Data/runtime/triggers/`.

El proceso sobrevive a reinicios del dashboard. Cuando el gestor vuelve a
arrancar, adopta el PID existente; si el proceso terminó y sigue habilitado, el
watchdog lo recupera automáticamente.

La ejecución manual de `.venv/bin/python telegram/bot.py` se mantiene sólo para
diagnóstico. No debe usarse al mismo tiempo que el proceso administrado porque
Telegram permite un único consumidor de `getUpdates` por token.

El bot se comunicará de forma transparente con el servidor REST de ADA en `http://127.0.0.1:5005/api/chat`.
