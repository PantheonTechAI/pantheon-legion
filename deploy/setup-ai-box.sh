#!/usr/bin/env bash
# Prepare the AI box to run Praetorium behind Caddy on loopback port 8106.
# Run as jtdauria from any directory.  It uses sudo only for system-owned files.

set -Eeuo pipefail

readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly repo_dir="$(cd -- "$script_dir/.." && pwd)"
readonly service_user="jtdauria"
readonly venv_dir="$repo_dir/.venv"
readonly config_dir="/etc/legion"
readonly env_file="$config_dir/praetorium.env"
readonly state_dir="/var/lib/legion"
readonly unit_file="/etc/systemd/system/legion-praetorium.service"

start_service=false

usage() {
    cat <<'EOF'
Usage: deploy/setup-ai-box.sh [--start]

Creates the project virtual environment, installs requirements, prepares the
Legion state/config directories, and installs/enables legion-praetorium.service.

The existing /etc/legion/praetorium.env is never overwritten. Review it before
starting the service. Pass --start only after Caddy proxies Legion to 127.0.0.1:8106.
EOF
}

if [[ $# -gt 1 ]]; then
    usage >&2
    exit 2
fi
if [[ $# -eq 1 ]]; then
    case "$1" in
        --start) start_service=true ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
fi

if [[ "$(id -un)" != "$service_user" ]]; then
    printf 'Run this script as %s, not %s.\n' "$service_user" "$(id -un)" >&2
    exit 1
fi
if ! python3 -m venv --help >/dev/null 2>&1; then
    printf 'python3 venv support is required; install the python3-venv package first.\n' >&2
    exit 1
fi

printf 'Creating or reusing %s\n' "$venv_dir"
python3 -m venv "$venv_dir"
"$venv_dir/bin/python" -m pip install --upgrade pip
"$venv_dir/bin/python" -m pip install --requirement "$repo_dir/requirements.txt"
"$venv_dir/bin/python" -c 'from langgraph.graph import StateGraph; import praetorium.deployment'

sudo install -d -o "$service_user" -g "$service_user" -m 0750 "$state_dir"
sudo install -d -o root -g "$service_user" -m 0750 "$config_dir"
if ! sudo test -e "$env_file"; then
    sudo install -o root -g "$service_user" -m 0640 \
        "$repo_dir/deploy/praetorium.env.example" "$env_file"
    printf 'Created %s from the example. Review its values before starting.\n' "$env_file"
else
    printf 'Preserved existing %s.\n' "$env_file"
fi

sudo install -o root -g root -m 0644 \
    "$repo_dir/deploy/systemd/legion-praetorium.service" "$unit_file"
sudo systemctl daemon-reload
sudo systemctl enable legion-praetorium.service

if "$start_service"; then
    sudo systemctl restart legion-praetorium.service
    sudo systemctl --no-pager --full status legion-praetorium.service
else
    printf 'Setup complete. After reviewing %s and the Caddy 8106 proxy, run:\n' "$env_file"
    printf '  %s --start\n' "$0"
fi
