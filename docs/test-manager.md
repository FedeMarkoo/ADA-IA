# ADA Test Manager

El gestor se ejecuta como `ada-test-manager`, escucha en `127.0.0.1:8088` y
persiste sus datos fuera del repositorio en `ADA_TEST_MANAGER_DATA_DIR`.

La imagen incluye `test-manager.seed.sqlite`, una base de fixtures versionada
que contiene únicamente casos de prueba. Al iniciar, el gestor importa por
nombre las categorías y prompts que todavía no existan en la base persistente;
no sobrescribe ejecuciones ni respuestas existentes y no duplica casos.
La base persistente contiene las tablas `categories`, `prompts` y
`executions`. La fixture no contiene filas de `executions`.

Las categorías incluidas actualmente son `Smoke tests`, `Clima` y `Google
Calendar`. Los casos de clima esperan `weather_current`; los de Calendar
esperan `calendar_upcoming_events`; el caso combinado espera ambas tools.

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

El gestor usa SQLite y la librería estándar de Python. No requiere instalar
dependencias de Node ni Python.
