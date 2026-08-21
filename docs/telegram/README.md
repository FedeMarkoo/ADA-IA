# Servidor y Bot Independiente de Telegram

El bot de Telegram está completamente desacoplado del núcleo de ADA y reside en su propia carpeta en la raíz: **`telegram/`**.

---

## 🏗️ Cómo Funciona

1. `telegram/bot.py` se conecta a la API de Telegram mediante *long-polling*.
2. Al recibir un mensaje o imagen, lo transforma en un payload estructurado y lo envía mediante HTTP POST al endpoint `/api/chat` de ADA.
3. Las imágenes adjuntas se descargan automáticamente en la carpeta `telegram_inbox/` y se envían a ADA para su análisis técnico/semántico.

---

## 🚀 Ejecución Independiente

### 1. Configuración de Credenciales (Bóveda Cifrada)
El token se almacena de forma segura en `~/Desktop/ADA_Data/vault.db` con AES-256:
- **Desde la UI**: Pestaña **Telegram Bot** → **🔑 Configurar Token**.
- **O por CLI**:
```bash
.venv/bin/python -c "from utils.credentials import SecureVault; SecureVault().set('telegram_bot_token', 'TU_TOKEN_DE_BOTFATHER')"
```

### 2. Inicio del Servidor
```bash
.venv/bin/python telegram/bot.py
```

### 3. Control desde el Dashboard
También podés iniciar, detener, reiniciar y verificar la conexión del bot con un solo clic desde la pestaña **📱 Telegram Bot** del Dashboard Gestor Web.
