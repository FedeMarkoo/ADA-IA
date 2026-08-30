# ADA Test Manager

El gestor se ejecuta como `ada-test-manager`, escucha en `127.0.0.1:8088` y
persiste sus datos fuera del repositorio en `ADA_TEST_MANAGER_DATA_DIR`.

La imagen no contiene una base SQLite ni prompts de prueba. Al iniciar, el
gestor crea el esquema en la base persistente y conserva categorías, prompts y
ejecuciones fuera del repositorio. Esto evita que los datos locales o las
ejecuciones terminen en CI o en la imagen Docker.

Cada caso puede declarar tools, memorias y contexto esperados. Al ejecutar un
caso, el gestor llama a ADA, conserva la respuesta y muestra los tokens totales,
los tokens por componente (`system`, `prompt`, `tools`, `memories`, etc.), modelo,
contexto seleccionado y tools efectivamente ejecutadas.

También envía la ejecución a un evaluador IA y combina ese resultado con checks
determinísticos. El resultado puede ser `pass`, `review` o `fail`. RAG se marca
como no disponible mientras ADA no tenga un proveedor RAG registrado; no se
considera exitoso por inferencia.

Los smoke tests incluyen términos esperados para comprobar que la respuesta
resuelve la consigna y no sólo devuelve una herramienta o un enlace. Si falta
cualquier término, la ejecución queda en `fail` aunque el evaluador IA sugiera
`pass`. El tiempo de espera se puede ajustar con `ADA_TIMEOUT_SECONDS`.

```bash
docker compose --env-file /ruta/a/ada-data/.env up -d --build ada-test-manager
open http://127.0.0.1:8088
```

El archivo de entorno es necesario porque Compose valida también las rutas de
los MCPs y de sus credenciales aunque sólo se reconstruya el gestor.

## Cargar una base existente

Prepará una carpeta externa y configurala en `ADA_TEST_MANAGER_DATA_DIR`:

```bash
mkdir -p /ruta/a/ada-test-manager-data
export ADA_TEST_MANAGER_DATA_DIR=/ruta/a/ada-test-manager-data
docker compose --env-file /ruta/a/ada-data/.env up -d --build ada-test-manager
```

Para restaurar una base respaldada, copiála únicamente dentro de esa carpeta
antes de iniciar el servicio. La ruta persistente esperada es:

```text
/ruta/a/ada-test-manager-data/test-manager.sqlite
```

No copies la base al repositorio ni a `test-manager/`. La base puede contener
ejecuciones y respuestas, por lo que debe tratarse como dato local.

### Cargar una categoría y un caso por API

El gestor crea las tablas automáticamente. Primero creá una categoría:

```bash
python3 - <<'PY'
import json
from urllib.request import Request, urlopen

def post(path, payload):
    request = Request(
        "http://127.0.0.1:8088" + path,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urlopen(request))

category = post("/api/categories", {"name": "Clima"})
test = {
    "category_id": category["id"],
    "name": "Pronóstico de mañana",
    "prompt": "¿Cómo va a estar el clima mañana?",
    "expected_tools": ["weather_current"],
    "expected_context": ["weather_current"],
    "expected_terms": ["mañana"],
}
print(category)
print(post("/api/prompts", test))
PY
```

También se pueden consultar las categorías con `GET /api/categories` y los
casos de una categoría con `GET /api/categories/{id}`. Para ejecutar un caso,
usá `POST /api/prompts/{id}/run`; la ejecución queda almacenada en la SQLite
externa.

El gestor usa SQLite y la librería estándar de Python. No requiere instalar
dependencias de Node ni Python.
