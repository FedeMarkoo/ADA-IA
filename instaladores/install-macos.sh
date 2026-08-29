#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_dir}"

command -v docker >/dev/null || {
    echo "Instala Docker Desktop para macOS y vuelve a ejecutar este instalador." >&2
    exit 1
}
docker compose version >/dev/null || { echo "Docker Compose no está disponible." >&2; exit 1; }

if [[ ! -f deploy/.env ]]; then
    cp deploy/.env.example deploy/.env
    echo "Se creó deploy/.env. Configúralo y vuelve a ejecutar el instalador."
    exit 1
fi

docker compose --env-file deploy/.env up -d --build
echo "ADA está disponible en http://localhost:8080 y el Test Manager en http://localhost:8088."
echo "Grafana: http://localhost:3000 | Prometheus: http://localhost:9090"
