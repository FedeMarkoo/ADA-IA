# ADA

ADA es un asistente local y extensible construido con Java 21, Maven y Spring Boot.
El proyecto se reinicia desde cero manteniendo los principios del sistema
anterior: local-first, privacidad, modularidad, trazabilidad, reversibilidad y
uso responsable de recursos.

## Estado actual

Esta primera iteración define la arquitectura, las reglas de desarrollo y los
contratos operativos. La implementación funcional se incorporará por cortes
pequeños y verificables.

## Documentación

- [Arquitectura](docs/architecture.md)
- [Reglas de código](docs/coding-rules.md)
- [Observabilidad y métricas](docs/observability.md)
- [Integraciones y configuración](docs/integrations.md)
- [Decisiones de arquitectura](docs/decisions/README.md)

## Principios no negociables

1. El dominio no conoce Spring, SQLite, LiteLLM ni proveedores externos.
2. Las dependencias apuntan hacia el dominio y los casos de uso.
3. Los componentes extensibles se consumen mediante listas de interfaces,
   nunca mediante `if`/`when` centralizados que conozcan todas las variantes.
4. Toda operación relevante deja métricas, logs estructurados y, cuando
   corresponde, un registro de auditoría.
5. Los datos locales viven fuera del repositorio mediante `ADA_DATA_DIR`.
6. Los secretos llegan por variables de entorno o un gestor externo; nunca por
   archivos versionados.

## Comandos previstos

```bash
mvn test
mvn verify
```

El despliegue local de LiteLLM y el layout de datos están documentados en
[Integraciones y configuración](docs/integrations.md). También hay instaladores
listos para [Linux, macOS y Windows](instaladores/README.md).

El smoke runner HTTP y el dashboard local de Grafana están documentados en
[Monitoreo local](monitoring/README.md).

## Versiones y releases

Los merges a `main` calculan automáticamente la siguiente versión semántica a
partir de los commits convencionales (`fix`, `feat` y cambios incompatibles).
El workflow crea el tag `vX.Y.Z`, el GitHub Release y dispara explícitamente
la construcción de las imágenes Docker `latest` y `X.Y.Z` para ADA y MCP. La
primera release usa `0.1.0`. El deployer sigue consumiendo `latest` por
defecto; para fijar una versión, configura `ADA_VERSION=X.Y.Z`.

## Instaladores multiplataforma

Los instaladores de `instaladores/` validan Docker, crean `../ada-data/.env`
desde el ejemplo cuando hace falta y levantan el stack completo con Docker
Compose. La configuración queda junto con las bases, backups y demás datos
persistentes, fuera del repositorio. Primero edita `../ada-data/.env` con tus
valores locales; no se deben versionar secretos.

### Linux

```bash
./instaladores/install-linux.sh
```

Para instalar además el autodeployer de `systemd`:

```bash
./instaladores/install-linux.sh --autodeployer
```

### macOS

Con Docker Desktop abierto:

```bash
./instaladores/install-macos.sh
```

### Windows

Con Docker Desktop abierto, desde PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\instaladores\install-windows.ps1
```

Las URLs locales son ADA `http://localhost:8080`, Test Manager
`http://localhost:8088`, Grafana `http://localhost:3000` y Prometheus
`http://localhost:9090`. Para detener el stack:

```bash
docker compose --env-file ../ada-data/.env down
```

Si definís `ADA_DATA_DIR`, reemplazá `../ada-data` por esa ruta en los
comandos y en la ubicación del archivo `.env`.

En Windows, ejecutar el mismo comando desde PowerShell.

## Inicio automático en Linux

El autodeployer mantiene levantado el stack de ADA, comprueba nuevas imágenes
cada cinco minutos y se reinicia si el proceso falla. Para instalarlo como
servicio `systemd`. Configura primero `../ada-data/.env` y asegúrate de que el
servicio pueda ejecutar Docker:

```bash
# Edita ../ada-data/.env y completa los secretos y rutas locales
sudo usermod -aG docker "$USER"
newgrp docker
./scripts/deployment/install-autodeployer.sh
```

El instalador habilita `ada-deployer.service` para cada arranque y lo inicia
en el momento. Para revisar el estado y los logs:

```bash
systemctl status ada-deployer.service
journalctl -u ada-deployer.service -f
```
