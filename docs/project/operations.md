# Operación y recursos

## Ejecutar

```bash
ada serve
```

Ese entrypoint mantiene compatibilidad con Flask. Para ASGI, instalá la extra
`web` y ejecutá `uvicorn ada.interfaces.web.asgi:create_app --factory`.
Para el worker autónomo, ejecutá `ada-autonomous`; usa SQLite como event store,
watchers de carpetas y scheduler con reintentos.

Para instalaciones reproducibles del runtime base, ejecutá
`python -m pip install -r requirements.lock`. Las extras opcionales siguen
declaradas en `pyproject.toml`.

## Pruebas

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Presupuesto de CPU

El perfil predeterminado prioriza no saturar el equipo durante lotes RAW:

- `photo_workers: 1`;
- `agent_max_workers: 1`;
- `ollama_num_thread: 2`;
- `cpu_limit_percent: 50`;
- pausa adaptativa si la carga ya está alta.

Esto limita la concurrencia y los hilos solicitados a Ollama. Puede haber picos
breves al decodificar un RAW; no es un límite duro impuesto por el kernel.

Las operaciones de archivos que mueven, copian, crean o eliminan requieren
confirmación, ofrecen `dry_run` y conservan un manifiesto para `undo`. No se
debe exponer Ollama ni la API de ADA directamente a internet.

## Credenciales

Gmail usa un token OAuth local y scopes separados para lectura/borradores/envío.
Los borradores reales requieren confirmación y el envío conserva un scope separado.
El almacén
cifrado opcional requiere `ADA_CREDENTIAL_KEY`; nunca se guarda un secreto en
`config.json` o Git. Instagram sólo ejecuta el script Node configurado, con
allowlist de rutas, confirmación explícita y un perfil persistente en
`instagram_profile_dir` para conservar cookies/sesión fuera del repositorio.

Para cifrar el contenido sensible de `memory.db`, instalá la extra
`credentials`, definí una clave Fernet en `ADA_MEMORY_KEY` y activá
`memory_encryption: true`. ADA migra las filas existentes al iniciar y usa
búsqueda local sin FTS sobre el contenido descifrado en memoria; la base y sus
backups siguen cifrados en disco.

## Servicio permanente

En Linux, copiá `deploy/ada.service` a `~/.config/systemd/user/ada.service`,
recargá `systemctl --user daemon-reload` y habilitá `systemctl --user enable --now ada`.
En Windows, desde PowerShell ejecutá
`./deploy/windows/install-ada-task.ps1 -AdaRoot (Get-Location).Path`; esto registra
el worker con el Programador de tareas y reinicia tras fallos.

El backup periódico del daemon se activa con `backup_interval_seconds` y
opcionalmente `backup_path` en la configuración. Las reglas de autonomía pueden
filtrar por `path_prefix`, `location`, `geofence` (`lat`, `lon`, `radius_m`) e
`inventory_max` para proactividad controlada.

Para lotes fotográficos CPU-bound se puede seleccionar el aislamiento por
procesos con `photo_executor: "process"` (o `executor: "process"` en la acción);
el valor predeterminado conserva threads para evitar el costo de crear procesos
cuando el lote es pequeño.
