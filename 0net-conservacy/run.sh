#!/usr/bin/env bash

CONFIG_FILE="/data/options.json"

if [ -f "$CONFIG_FILE" ]; then
    ENABLE_TOR=$(jq -r '.ENABLE_TOR // "false"' "$CONFIG_FILE")
    UI_PASSWORD=$(jq -r '.UI_PASSWORD // ""' "$CONFIG_FILE")
else
    echo "No se encontró $CONFIG_FILE, usando valores por defecto."
    ENABLE_TOR="false"
    UI_PASSWORD=""
fi

export ENABLE_TOR
export UI_PASSWORD

exec python3 /home/service-0net/zeronet.py --ui_ip "*" --fileserver_port 26552 \
    --tor $TOR_ENABLED --tor_controller tor:$TOR_CONTROL_PORT \
    --tor_proxy tor:$TOR_SOCKS_PORT --tor_password $TOR_CONTROL_PASSWD
