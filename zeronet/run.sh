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

exec /usr/local/bin/run.sh
