# Pruebas de prompts

ADA tiene dos mecanismos de prueba que no deben confundirse:

- El smoke runner HTTP (`scripts/testing/run-smoke-prompts.py`) conserva su
  semilla en la SQLite externa de ADA, en la tabla `smoke_prompts`.
- ADA Test Manager (`test-manager/`) usa una SQLite propia con las tablas
  `categories`, `prompts` y `executions`. La base se persiste fuera del
  repositorio mediante `ADA_TEST_MANAGER_DATA_DIR`.

Ejemplo local:

```bash
python3 scripts/testing/run-smoke-prompts.py \
  --database /ruta/a/ada-data/db/ada.sqlite \
  --seed-file scripts/testing/smoke-prompts.json \
  --limit 3
```

Para ejecutar casos ya cargados, se omite `--seed-file`. La variable
`ADA_DATA_DIR` también permite seleccionar la carpeta externa por defecto.

Para usar el gestor visual, levantá `ada-test-manager` y abrí
`http://127.0.0.1:8088`. La base externa se crea con el esquema vacío al primer
inicio. Los casos se cargan por la API documentada en
`docs/test-manager.md`; cada caso declara herramientas, contexto y términos
esperados. El gestor ejecuta el prompt contra ADA, guarda la ejecución en su
propia SQLite y combina una evaluación IA con checks determinísticos.
