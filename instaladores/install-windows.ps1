$ErrorActionPreference = "Stop"

$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectDir

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Instala Docker Desktop para Windows y vuelve a ejecutar este instalador."
}
docker compose version | Out-Null

$EnvFile = Join-Path $ProjectDir "deploy\.env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $ProjectDir "deploy\.env.example") $EnvFile
    Write-Host "Se creó deploy\.env. Configúralo y vuelve a ejecutar el instalador."
    exit 1
}

docker compose --env-file $EnvFile up -d --build
Write-Host "ADA: http://localhost:8080 | Test Manager: http://localhost:8088"
Write-Host "Grafana: http://localhost:3000 | Prometheus: http://localhost:9090"
