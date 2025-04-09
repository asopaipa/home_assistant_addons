#!/bin/bash

CONFIG_FILE="/data/options.json"

if [ -f "$CONFIG_FILE" ]; then
    UI_USERNAME=$(jq -r '.UI_USERNAME // "user"' "$CONFIG_FILE")
    UI_PASSWORD=$(jq -r '.UI_PASSWORD // "user"' "$CONFIG_FILE")
    ACESTREAM_PORT=$(jq -r '.ACESTREAM_PORT // "6878"' "$CONFIG_FILE")
    SLUG_ZERONET=$(jq -r '.SLUG_ZERONET // ""' "$CONFIG_FILE")
else
    echo "No se encontró $CONFIG_FILE, usando valores por defecto."
    UI_USERNAME="user"
    UI_PASSWORD="user"
    ACESTREAM_PORT="6878"
    SLUG_ZERONET=""
fi


# Exportar la variable de entorno para el puerto
export PORTACE=$ACESTREAM_PORT


if [ -n "$ACESTREAM_PORT" ]; then
    sed -i "s/6878/$ACESTREAM_PORT/g" /static/js/main.js
    sed -i "s/6878/$ACESTREAM_PORT/g" /getLinks.py
fi

if [ -n "$UI_USERNAME" ]; then
    sed -i "s/USERNAME = \"\"/USERNAME = \"$UI_USERNAME\"/g" /app.py
    sed -i "s/PASSWORD = \"\"/PASSWORD = \"$UI_PASSWORD\"/g" /app.py
fi


if [ -n "$SLUG_ZERONET" ]; then
    sed -i "s|config_zeronet_ws_url|\"ws://$SLUG_ZERONET:43110/Websocket\"|g" /app/app.py
else
    sed -i "s|config_zeronet_ws_url|\"ws://127.0.0.1:43110/Websocket\"|g" /app/app.py
fi

#cd /app
#exec python app.py

set -e

mkdir -p /share/aceWebPlayer
#cd /app
exec python app.py -d /share/aceWebPlayer
