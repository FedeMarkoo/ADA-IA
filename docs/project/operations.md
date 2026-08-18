# Operación y recursos

## Ejecutar

```bash
cd /Users/home/Desktop/ADA
.venv/bin/python ada.py serve
```

Ese es el entrypoint oficial: levanta la UI web y el agente ADA en el mismo
proceso. La UI es una interfaz de `application/agent`, no un servicio separado.
`ui_server.py` queda únicamente como entrypoint de compatibilidad.

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
confirmación. No se debe exponer Ollama ni la API de ADA directamente a internet.
