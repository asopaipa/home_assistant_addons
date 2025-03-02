#!/usr/bin/env bash

CONFIG_FILE="/data/options.json"

if [ -f "$CONFIG_FILE" ]; then
    ENABLE_TOR=$(jq -r '.ENABLE_TOR // "false"' "$CONFIG_FILE")
    UI_PASSWORD=$(jq -r '.UI_PASSWORD // ""' "$CONFIG_FILE")
    TOR_CONTROL_PORT=$(jq -r '.TOR_CONTROL_PORT // "9151"' "$CONFIG_FILE")
    TOR_SOCKS_PORT=$(jq -r '.TOR_SOCKS_PORT // "9150"' "$CONFIG_FILE")
    PORT_FILESERVER=$(jq -r '.ports["26552/tcp"] // 26552' "$CONFIG_FILE")
    TOR_CONTROL_PASSWD=$(jq -r '.TOR_CONTROL_PASSWD // "changeme"' "$CONFIG_FILE")
    
else
    echo "No se encontró $CONFIG_FILE, usando valores por defecto."
    ENABLE_TOR="false"
    UI_PASSWORD=""
    TOR_CONTROL_PORT="9151"
    TOR_SOCKS_PORT="9150"
    PORT_FILESERVER="26552"
    TOR_CONTROL_PASSWD="changeme"
fi

export ENABLE_TOR
export UI_PASSWORD
export TOR_CONTROL_PORT
export TOR_SOCKS_PORT
export TOR_CONTROL_PASSWD

exec python3 /home/service-0net/start-venv.py --ui_ip "*" --fileserver_port $PORT_FILESERVER \
    --tor $ENABLE_TOR --tor_controller tor:$TOR_CONTROL_PORT \
    --tor_proxy tor:$TOR_SOCKS_PORT --tor_password $TOR_CONTROL_PASSWD --ui_password $UI_PASSWORD
