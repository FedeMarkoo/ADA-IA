#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_dir}"

data_dir="${ADA_DATA_DIR:-${project_dir}/../ada-data}"
if [[ "${data_dir}" != /* ]]; then
    data_dir="${project_dir}/${data_dir}"
fi
mkdir -p "${data_dir}"
data_dir="$(cd -- "${data_dir}" && pwd -P)"
env_file="${data_dir}/.env"

command -v docker >/dev/null || {
    echo "Instala Docker Desktop para macOS y vuelve a ejecutar este instalador." >&2
    exit 1
}
docker compose version >/dev/null || { echo "Docker Compose no está disponible." >&2; exit 1; }

created_env=false
if [[ ! -f "${env_file}" ]]; then
    cp deploy/.env.example "${env_file}"
    chmod 600 "${env_file}"
    created_env=true
fi

docker compose --env-file "${env_file}" up -d --build
echo "ADA está disponible en http://localhost:8080 y el Test Manager en http://localhost:8088."
echo "Grafana: http://localhost:3000 | Prometheus: http://localhost:9090"
if [[ "${created_env}" == true ]]; then
    echo "Se creó ${env_file} con valores locales seguros para arrancar. Telegram queda deshabilitado; edita ese archivo para configurarlo."
fi
