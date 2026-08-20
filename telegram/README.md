# Servidor Independiente de Telegram Bot para ADA

Este módulo actúa como un **servidor y cliente de mensajería independiente** desacoplado del núcleo de ADA.

---

## 🚀 Cómo Ejecutar el Bot

1. Configurá tu token de Telegram:
   ```bash
   export TELEGRAM_BOT_TOKEN="tu-token-aqui"
   export TELEGRAM_ALLOWED_CHAT_IDS="123456789" # Opcional pero recomendado
   ```
2. Ejecutá el servidor del bot de forma independiente:
   ```bash
   .venv/bin/python telegram/bot.py
   ```

El bot se comunicará de forma transparente con el servidor REST de ADA en `http://127.0.0.1:5005/api/chat`.
