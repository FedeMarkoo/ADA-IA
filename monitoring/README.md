# Monitoreo local

El dashboard versionado de Grafana está en
`monitoring/grafana/dashboards/ada-smoke.json`. Usa Prometheus como fuente y
observa requests, llamadas al modelo y tokens por componente.

La prueba manual se ejecuta con:

```bash
python3 scripts/testing/run-smoke-prompts.py
```

También puede consumir el export de prompts respaldado fuera del repositorio:

```bash
python3 scripts/testing/run-smoke-prompts.py \
  --prompts-file /home/fedemarkoo/Desktop/ADA_Data/backups/<backup>/healthcheck-prompts.json
```

Para que Grafana pueda consultar las métricas, debe existir un Prometheus en
`http://127.0.0.1:9090` scrapeando `http://127.0.0.1:8081/actuator/prometheus`.
El dashboard se importa con `scripts/testing/provision-grafana.py`.
