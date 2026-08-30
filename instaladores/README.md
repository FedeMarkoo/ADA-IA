# Instaladores de ADA

Estos scripts levantan ADA, LiteLLM, Ollama, MCPs, Test Manager, Grafana y
Prometheus mediante Docker Compose. Requieren Docker Desktop en macOS/Windows
o Docker Engine con Compose en Linux.

El instalador crea `../ada-data/.env` si todavía no existe y levanta el stack
con valores locales iniciales. La configuración queda junto con las bases y
backups, fuera del repositorio. Telegram queda deshabilitado hasta completar
`ADA_TELEGRAM_BOOTSTRAP_BOT_TOKEN`, `ADA_TELEGRAM_BOOTSTRAP_CHAT_ID` y
`ADA_SECRET_MASTER_KEY`, y cambiar `ADA_TELEGRAM_ENABLED=true`.

Si preferís prepararlo manualmente:

```bash
mkdir -p ../ada-data
cp deploy/.env.example ../ada-data/.env
chmod 600 ../ada-data/.env
```

`LITELLM_MASTER_KEY` y `ADA_GDRIVE_PATH` ya tienen valores locales para que
Compose no falle por variables obligatorias. Cambiá esos valores antes de un
entorno compartido o productivo.

## Linux

```bash
./instaladores/install-linux.sh
```

Para instalar también el servicio `systemd` del autodeployer:

```bash
./instaladores/install-linux.sh --autodeployer
```

El autodeployer requiere permisos de administrador durante la instalación.

## macOS

Abre Docker Desktop y ejecuta:

```bash
./instaladores/install-macos.sh
```

## Windows

Abre Docker Desktop y ejecuta PowerShell en la raíz del repositorio:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\instaladores\install-windows.ps1
```

## Verificación

Después de levantar el stack:

- ADA: <http://localhost:8080>
- Test Manager: <http://localhost:8088>
- Grafana: <http://localhost:3000>
- Prometheus: <http://localhost:9090>

Para detenerlo, ejecuta `docker compose --env-file ../ada-data/.env down`.
