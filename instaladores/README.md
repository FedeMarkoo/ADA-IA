# Instaladores de ADA

Estos scripts levantan ADA, LiteLLM, Ollama, MCPs, Test Manager, Grafana y
Prometheus mediante Docker Compose. Requieren Docker Desktop en macOS/Windows
o Docker Engine con Compose en Linux.

Antes de ejecutar uno, configura `deploy/.env`. Si todavía no existe, el script
crea una copia de `deploy/.env.example` y termina para que puedas completar la
configuración sin arrancar con valores de ejemplo.

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

Para detenerlo, ejecuta `docker compose --env-file deploy/.env down`.
