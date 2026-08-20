# Telegram y Ollama

Ollama es el backend local actual. ADA puede iniciarlo si está instalado y la
configuración lo permite. Telegram sería un adaptador de entrada y salida, no
el lugar donde vive la lógica de negocio.

## Modelos

```bash
ollama pull llama3.2:3b
ollama pull qwen2.5vl:3b
```

## Telegram

La integración de bot requiere un token de BotFather. El token debe vivir solo
en `TELEGRAM_BOT_TOKEN` y nunca en Git. ADA implementa long polling dentro del
proceso iniciado con `ada serve`: recibe texto o imágenes, descarga las
imágenes en `telegram_inbox/` y reenvía el pedido al endpoint interno
`POST /api/chat`.

La UI web y Telegram pasan por el mismo endpoint y, por lo tanto, comparten
parser, agentes, capabilities, memoria, confirmaciones y formato de respuesta.
Telegram es un adapter de entrada/salida; no contiene lógica de negocio.

### Configuración

```bash
export TELEGRAM_BOT_TOKEN='token-entregado-por-botfather'
export TELEGRAM_ALLOWED_CHAT_IDS='123456789'
.venv/bin/ada serve
```

Para diagnóstico detallado:

```bash
.venv/bin/ada serve -debug
```

La ejecución escribe un log con el timestamp de inicio en
`/Users/home/Desktop/logs/ada-debug-YYYYMMDD-HHMMSS.log`, además de mostrarlo
en la terminal. El archivo registra `chat_id`, mensaje recibido, router,
clasificador de comida, asesor, respuesta y errores; nunca registra el token.

`TELEGRAM_ALLOWED_CHAT_IDS` es opcional, pero recomendado: si se informa,
ADA solo responde a esos chats. Telegram queda desactivado si no hay token.

WhatsApp requiere evaluar costos, límites y API oficial antes de implementarlo.

Después de modificar el código hay que reiniciar el proceso. Si aparece
`Address already in use`, hay otra instancia usando el puerto 5005; detenela
con `Ctrl+C` antes de volver a iniciar ADA.
