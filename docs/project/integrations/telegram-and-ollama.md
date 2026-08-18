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
en una variable de entorno y nunca en Git. El adaptador todavía debe convertirse
en un servicio completo con recepción de texto, imágenes, comandos, errores y
auditoría.

WhatsApp requiere evaluar costos, límites y API oficial antes de implementarlo.
