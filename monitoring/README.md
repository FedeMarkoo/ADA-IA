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
  --prompts-file "$ADA_DATA_DIR/backups/<backup>/healthcheck-prompts.json"
```

Para que Grafana pueda consultar las métricas, debe existir un Prometheus en
`http://127.0.0.1:9090` scrapeando `http://127.0.0.1:8081/actuator/prometheus`.
El dashboard se importa con `scripts/testing/provision-grafana.py`.

## Deploy local

Copiá `deploy/.env.example` a `deploy/.env` y completá los secretos fuera del
repositorio. El gestor local verifica la imagen con `docker compose pull`,
compara el ID local, respalda SQLite, redeploya solo cuando cambió, espera el
healthcheck y vuelve a la imagen anterior si la aplicación no queda saludable:

```bash
python3 scripts/deployment/local-deployer.py --once
```

Para dejarlo monitoreando cada cinco minutos:

```bash
python3 scripts/deployment/local-deployer.py --interval 300
```

En Linux puede instalarse `deploy/ada-deployer.service` bajo systemd. El
gestor no ejecuta comandos construidos desde la imagen ni guarda credenciales.
