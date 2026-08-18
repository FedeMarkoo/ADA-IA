# Telegram con motor local

## Estado actual

ADA usa Ollama como motor local. Telegram funciona como interfaz de entrada y
salida: los mensajes llegan al proceso de ADA, que los deriva al modelo local.
No se necesita una clave de OpenAI ni una clave de otro proveedor para este
flujo.

El bot de Telegram sí necesita un token emitido por `@BotFather`. Ese token es
un secreto operativo y no debe guardarse en el repositorio, en un archivo
versionado ni en mensajes de commit.

## Preparación de Ollama

Instalar Ollama y descargar los modelos configurados:

```bash
ollama serve
ollama pull llama3.2:3b
ollama pull qwen2.5vl:3b
```

`llama3.2:3b` se usa para conversación y `qwen2.5vl:3b` para análisis visual.
Los nombres se pueden cambiar en `config.json` mediante `ollama_model` y
`vision_model`.

## Variables de entorno

Configurar el token de Telegram únicamente en la sesión que ejecuta el bot:

```bash
export TELEGRAM_BOT_TOKEN='TOKEN_EMITIDO_POR_BOTFATHER'
```

No usar valores reales en `config.json`, `.env`, documentación o ejemplos
versionados. Si un token se expone, revocarlo inmediatamente desde BotFather y
emitir uno nuevo.

La URL local de Ollama puede cambiarse sin modificar código:

```bash
export ADA_OLLAMA_URL='http://127.0.0.1:11434'
```

## Ejecución y prueba

Con el entorno virtual activo:

```bash
python -m pip install -r requirements.txt
python ada.py
```

Para probar la integración de Telegram, iniciar el adaptador configurado para
ADA y enviar `/start` al bot. Luego probar un mensaje de texto y una imagen.
El proceso debe permanecer ejecutándose; detenerlo con `Ctrl+C`.

## Privacidad y límites

- El modelo se ejecuta en el equipo local a través de `127.0.0.1`.
- Telegram sigue siendo un servicio externo: los mensajes enviados al bot
  pasan por Telegram antes de llegar a ADA.
- Los modelos descargados no deben agregarse al repositorio. `.gitignore`
  excluye artefactos grandes y archivos de entorno.
- Las acciones que modifican archivos deben conservar la confirmación de
  riesgo definida en `config.json`.

## Auditoría de secretos

Antes de publicar cambios, revisar archivos versionados con una herramienta de
detección de secretos y comprobar que no haya valores junto a variables como
`TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY` o `ANTHROPIC_API_KEY`. Las variables
pueden aparecer como nombres en el código; lo que no debe aparecer son sus
valores.
