# Integraciones y configuración

## LiteLLM

ADA no acopla el dominio a un SDK de proveedor. El adaptador de salida habla
con el endpoint compatible con OpenAI de LiteLLM. El modelo se configura como
`provider/model` y la política de selección decide cuál usar.

Variables principales:

```text
ADA_LLM_BASE_URL=http://127.0.0.1:4000
ADA_LLM_API_KEY=...
ADA_LLM_DEFAULT_MODEL=openai/gpt-4o-mini
```

Cuando ADA usa el LiteLLM incluido en Compose, `ADA_LLM_API_KEY` debe coincidir
con `LITELLM_MASTER_KEY`. Si no se define explícitamente, Compose la hereda de
`LITELLM_MASTER_KEY` automáticamente.

No se guardan claves en `application.yml`, SQLite ni logs. Timeouts, reintentos,
backoff y circuit breaker deben ser explícitos y medidos.

### Ollama local en Docker

El `compose.yaml` incluye Ollama como proveedor local de LiteLLM. El modelo se
descarga una sola vez mediante el servicio de inicialización `ollama-model` y
queda persistido en el volumen Docker nombrado `ollama-data`; por eso un
reinicio o un redeploy no elimina los modelos descargados. El modelo se puede
cambiar sin modificar el código:

```text
OLLAMA_MODEL=llama3.2:1b
ADA_LLM_DEFAULT_MODEL=ollama/llama3.2:1b
```

En un clon nuevo, calculá la carpeta persistente desde la raíz del repositorio
y pasala explícitamente a Compose:

```bash
repo_dir="$(pwd -P)"
data_dir="$(realpath -m "${repo_dir}/../ada-data")"
mkdir -p "${data_dir}"
cp deploy/.env.example "${data_dir}/.env"
docker compose --project-directory "${repo_dir}" \
  --env-file "${data_dir}/.env" up -d
```

El autodeployer usa la misma raíz del repositorio y recibe la ruta absoluta a
`${data_dir}/.env` al instalar el servicio. No debe iniciarse `systemd` desde
otra carpeta ni depender de un `.env` del directorio personal: Compose y el
deployer deben leer siempre el archivo persistente junto a las bases.

Compose espera a que Ollama esté
saludable, descarga el modelo configurado y recién después inicia LiteLLM y
ADA. El puerto de Ollama queda limitado a `127.0.0.1:11434` para diagnóstico
local; LiteLLM lo consume por la red interna de Compose.

## MCP de búsqueda web

Los servidores MCP externos a ADA viven en `mcp/<nombre>` y se distribuyen en
una única imagen `ghcr.io/fedemarkoo/ada-mcps`. El gateway implementa el
transporte JSON-RPC y mantiene endpoints internos por servidor: `/web-search`
expone `web_search` y `/filesystem` expone las tools de filesystem. ADA publica
esas tools mediante sus providers y las ejecuta mediante sus adapters Java.

Compose levanta los MCPs en la red interna mediante el servicio `ada-mcps`.
No se publica el puerto al host. Para agregar otra tool, se incorpora al
gateway y al mismo contexto `mcp/`, junto con su adapter correspondiente en
`infrastructure.out`.

El MCP `filesystem` monta el Google Drive local como solo lectura en `/gdrive`.
La ruta del host se configura mediante `ADA_GDRIVE_PATH`, por ejemplo
`ADA_GDRIVE_PATH=<ruta-del-host>/GoogleDrive`. El servidor solo autoriza `/data`
y `/gdrive`, y resuelve las rutas antes de validarlas para impedir escapes con
`..` o enlaces simbólicos.

El endpoint de gestión queda atado a `127.0.0.1:8081`; así Prometheus y los
endpoints de Actuator no quedan expuestos por la interfaz HTTP de la aplicación.
En un despliegue remoto debe agregarse autenticación o una ACL de red.

## Telegram

ADA puede recibir mensajes y enviar respuestas, además de enviar notificaciones
de ciclo de vida, a un chat de Telegram mediante un bot. La función está
desactivada por defecto y usa long polling, por lo que no requiere exponer un
webhook público. El token y el chat ID se guardan cifrados con AES-GCM en
`ada_secrets`; la clave maestra nunca se guarda en SQLite:

```text
ADA_TELEGRAM_ENABLED=true
ADA_SECRET_MASTER_KEY=<base64 de 32 bytes>
ADA_TELEGRAM_BOOTSTRAP_BOT_TOKEN=...
ADA_TELEGRAM_BOOTSTRAP_CHAT_ID=...
```

Las variables `ADA_TELEGRAM_BOOTSTRAP_*` solo se usan para insertar el secreto
si todavía no existe; luego pueden retirarse del entorno. Generá la clave, por
ejemplo, con `openssl rand -base64 32`. Los errores de Telegram no impiden
iniciar ni apagar ADA y no se registran tokens ni credenciales.

Una vez iniciada ADA con `ADA_TELEGRAM_ENABLED=true`, el bot consulta mensajes
nuevos y solo procesa mensajes del chat cuyo ID coincide con el chat ID
configurado. Cada mensaje se ejecuta como una conversación con ID
`telegram:<chat-id>` y la respuesta se envía al mismo chat. Para obtener el
chat ID, enviá primero un mensaje al bot y consultá `getUpdates` de Telegram;
el valor debe quedar en `ADA_TELEGRAM_BOOTSTRAP_CHAT_ID` durante el primer
inicio.

## Automatizaciones

ADA puede iniciar conversaciones mediante programaciones persistidas en SQLite.
El scheduler consulta los disparadores periódicamente y ejecuta su prompt por
el mismo caso de uso que una conversación HTTP o Telegram; la respuesta se
envía por el canal de salida configurado.

El scheduler despierta cada segundo y consulta un índice de SQLite por las filas
vencidas; si no hay ninguna, no ejecuta el modelo ni realiza llamadas externas.
El horario usa la sintaxis cron de Spring, con seis campos incluyendo los
segundos. La programación, la zona horaria y el prompt viven en la tabla
`scheduled_triggers`, no en variables de entorno.

El MCP `weather_current` obtiene clima y ubicación mediante servicios externos.
En una tarea programada de tipo `weather`, ADA precarga ese dato antes de llamar
al modelo; así no carga el catálogo MCP ni hace una segunda vuelta de herramientas.

También se pueden cargar disparadores adicionales mediante `POST
/api/v1/schedules`:

```json
{
  "name": "daily-summary",
  "eventType": "weather",
  "cronExpression": "0 30 9 * * *",
  "timezone": "America/Argentina/Buenos_Aires",
  "prompt": "Usá los datos meteorológicos precargados y enviame un resumen breve para comenzar el día.",
  "conversationId": "autonomy-summary",
  "enabled": true
}
```

## SQLite fuera del repositorio

`ADA_DATA_DIR` es obligatorio en entornos no efímeros y por defecto debe
apuntar a una carpeta hermana del repositorio, por ejemplo:

```text
../ada-data/
├── db/         ada.sqlite, WAL y archivos temporales
├── logs/       ada.log y archivos rotados de hasta 10 MB
├── backups/    copias verificadas
├── exports/    salidas generadas
├── models/     artefactos locales grandes
└── runtime/    locks, pid y archivos efímeros
```

La aplicación recibe la ruta por configuración; ningún adaptador construye
rutas relativas al directorio de trabajo. SQLite usa WAL, migraciones
versionadas y conexiones configuradas para concurrencia segura.

## Secretos y entornos

Se versiona únicamente configuración segura de ejemplo. Desarrollo, CI y
producción deben poder inyectar valores sin modificar el código.
