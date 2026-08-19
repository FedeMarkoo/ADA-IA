# Operación y recursos

## Ejecutar

```bash
ada serve
```

Ese entrypoint mantiene compatibilidad con Flask. Para ASGI, instalá la extra
`web` y ejecutá `uvicorn ada.interfaces.web.asgi:create_app --factory`.
Para el worker autónomo, ejecutá `ada-autonomous`; usa SQLite como event store,
watchers de carpetas y scheduler con reintentos.

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

Gmail usa un token OAuth local y scopes separados para lectura/envío. El almacén
cifrado opcional requiere `ADA_CREDENTIAL_KEY`; nunca se guarda un secreto en
`config.json` o Git. Instagram sólo ejecuta el script Node configurado, con
allowlist de rutas y confirmación explícita.

## Servicio permanente

En Linux, copiá `deploy/ada.service` a `~/.config/systemd/user/ada.service`,
recargá `systemctl --user daemon-reload` y habilitá `systemctl --user enable --now ada`.
