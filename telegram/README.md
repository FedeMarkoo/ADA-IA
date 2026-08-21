# Servidor Independiente de Telegram Bot para ADA

Este módulo actúa como un **servidor y cliente de mensajería independiente** desacoplado del núcleo de ADA.

---

## 🚀 Cómo Ejecutar el Bot

1. Configurá tu token en la **Bóveda Cifrada (`vault.db`)**:
   - **Desde el Gestor Web**: Ingresá en `http://127.0.0.1:5005` → Pestaña **Telegram Bot** → **🔑 Configurar Token**.
   - **O por CLI**:
     ```bash
     .venv/bin/python -c "from utils.credentials import SecureVault; SecureVault().set('telegram_bot_token', 'TU_TOKEN_DE_BOTFATHER')"
     ```

2. Ejecutá el servidor del bot de forma independiente:
   ```bash
   .venv/bin/python telegram/bot.py
   ```

El bot se comunicará de forma transparente con el servidor REST de ADA en `http://127.0.0.1:5005/api/chat`.
