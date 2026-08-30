#!/usr/bin/env bash
set -Eeuo pipefail

service_name="ada-deployer.service"
service_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../deploy" && pwd)/${service_name}"
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
data_dir="${ADA_DATA_DIR:-${project_dir}/../ada-data}"
if [[ "${data_dir}" != /* ]]; then
    data_dir="${project_dir}/${data_dir}"
fi
data_dir="$(realpath -m -- "${data_dir}")"
env_file="${data_dir}/.env"
service_target="/etc/systemd/system/${service_name}"
ada_user="$(id -un)"

if [[ "${EUID}" -ne 0 ]]; then
    exec sudo env ADA_DATA_DIR="${data_dir}" "$0" "$@"
fi

# sudo re-executes this script as root; SUDO_USER keeps the account that owns
# the project and must be the account running the Docker Compose deployer.
ada_user="${SUDO_USER:-${ada_user}}"
ada_group="$(id -gn "${ada_user}")"

if [[ ! -f "${env_file}" ]]; then
    template="${project_dir}/deploy/.env.example"
    if [[ ! -f "${template}" ]]; then
        echo "No existe la plantilla de configuración: ${template}" >&2
        exit 1
    fi
    install -o "${ada_user}" -g "${ada_group}" -m 0600 "${template}" "${env_file}"
    echo "Se creó ${env_file}; completá las credenciales antes de activar Telegram."
fi

# Docker prepara los datos con el UID/GID del contenedor. El deployer necesita
# escribir sólo los backups, por lo que se habilita acceso grupal acotado.
mkdir -p "${data_dir}/backups"
chown "${ada_user}:${ada_group}" "${data_dir}/backups"
chmod 0770 "${data_dir}/backups"

if ! id -nG "${ada_user}" | tr ' ' '\n' | grep -qx docker; then
    echo "El usuario ${ada_user} no pertenece al grupo docker. Añádelo con: sudo usermod -aG docker ${ada_user}" >&2
    exit 1
fi

escape_sed_replacement() {
    printf '%s' "$1" | sed 's/[&|\\]/\\&/g'
}

set_env_value() {
    local key="$1"
    local value="$2"
    local escaped_value
    escaped_value="$(escape_sed_replacement "${value}")"
    if grep -q "^${key}=" "${env_file}"; then
        sed -i "s|^${key}=.*|${key}=${escaped_value}|" "${env_file}"
    else
        printf '%s=%s\n' "${key}" "${value}" >> "${env_file}"
    fi
}

# Compose resolves relative volume paths from its project directory. Persisting
# the normalized path in the data .env keeps the service correct even when the
# repository is reached through a symlink such as ~/Desktop/ADA-IA.
set_env_value "ADA_DATA_DIR" "${data_dir}"
if grep -q '^ADA_GDRIVE_PATH=../ada-data$' "${env_file}"; then
    set_env_value "ADA_GDRIVE_PATH" "${data_dir}"
fi
# The container owns the data directory with its runtime UID. Pre-create the
# deployer's lock as the host user so systemd does not need directory write
# access just to coordinate concurrent checks.
install -o "${ada_user}" -g "${ada_group}" -m 0660 /dev/null "${data_dir}/.deploy.lock"

rendered_service="$(mktemp)"
trap 'rm -f -- "${rendered_service}"' EXIT
sed \
    -e "s|@ADA_DIR@|$(escape_sed_replacement "${project_dir}")|g" \
    -e "s|@ADA_ENV_FILE@|$(escape_sed_replacement "${env_file}")|g" \
    -e "s|@ADA_USER@|$(escape_sed_replacement "${ada_user}")|g" \
    -e "s|@ADA_GROUP@|$(escape_sed_replacement "${ada_group}")|g" \
    "${service_source}" > "${rendered_service}"

install -o root -g root -m 0644 "${rendered_service}" "${service_target}"
systemctl daemon-reload
systemctl enable --now "${service_name}"

echo "ADA autodeployer instalado y habilitado al iniciar Linux."
echo "Estado: systemctl status ${service_name}"
echo "Logs:   journalctl -u ${service_name} -f"
