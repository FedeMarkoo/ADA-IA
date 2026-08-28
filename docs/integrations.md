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

En un clon nuevo, copiar `deploy/.env.example` a `deploy/.env` y ejecutar
`docker compose --env-file deploy/.env up -d`. Compose espera a que Ollama esté
saludable, descarga el modelo configurado y recién después inicia LiteLLM y
ADA. El puerto de Ollama queda limitado a `127.0.0.1:11434` para diagnóstico
local; LiteLLM lo consume por la red interna de Compose.

El endpoint de gestión queda atado a `127.0.0.1:8081`; así Prometheus y los
endpoints de Actuator no quedan expuestos por la interfaz HTTP de la aplicación.
En un despliegue remoto debe agregarse autenticación o una ACL de red.

## SQLite fuera del repositorio

`ADA_DATA_DIR` es obligatorio en entornos no efímeros y por defecto debe
apuntar a una carpeta hermana del repositorio, por ejemplo:

```text
../ada-data/
├── db/         ada.sqlite, WAL y archivos temporales
├── logs/       logs locales rotados
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
