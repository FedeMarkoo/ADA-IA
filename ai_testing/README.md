# ADA AI Testing

Catálogo y runner de pruebas conversacionales seguras. Los casos están en
`prompts.json`; no se ejecutan prompts fuera del catálogo y se bloquean verbos
mutantes antes de llamar a ADA.

```bash
.venv/bin/python ai_testing/runner.py
.venv/bin/python ai_testing/runner.py --case drive_folder_resolution
```

Cada ejecución sobrescribe `ai_testing/results.json` con el prompt, respuesta,
latencia, evaluación y métricas agregadas de la última corrida. Además, conserva
el histórico completo en `~/Desktop/ADA_Data/ai_testing.db`, incluyendo el commit
de Git de cada corrida. La evaluación base verifica errores, tiempo máximo y
criterios esperados; se puede extender con un juez LLM sin cambiar ADA.
