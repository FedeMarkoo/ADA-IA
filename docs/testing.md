# Pruebas de prompts

El smoke test usa la SQLite externa de ADA y no guarda bases de datos dentro del
repositorio. La tabla `smoke_prompts` se crea automáticamente en la base
montada y contiene el identificador, nombre, texto y estado habilitado de cada
caso.

El archivo `scripts/testing/smoke-prompts.json` es únicamente una semilla
reproducible. El runner primero hace upsert de esa semilla y después lee los
casos desde SQLite; la ejecución nunca usa prompts hardcodeados.

Ejemplo local:

```bash
python3 scripts/testing/run-smoke-prompts.py \
  --database /ruta/a/ADA_Data/java-deploy/db/ada.sqlite \
  --seed-file scripts/testing/smoke-prompts.json \
  --limit 3
```

Para ejecutar casos ya cargados, se omite `--seed-file`. La variable
`ADA_DATA_DIR` también permite seleccionar la carpeta externa por defecto.
