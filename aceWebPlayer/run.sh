#!/bin/bash

CONFIG_FILE="/data/options.json"

if [ -f "$CONFIG_FILE" ]; then
    UI_USERNAME=$(jq -r '.UI_USERNAME // "user"' "$CONFIG_FILE")
    UI_PASSWORD=$(jq -r '.UI_PASSWORD // "user"' "$CONFIG_FILE")
else
    echo "No se encontró $CONFIG_FILE, usando valores por defecto."
    UI_USERNAME="user"
    UI_PASSWORD="user"
fi


if [ -n "$UI_USERNAME" ]; then
    sed -i "s/USERNAME = \"\"/USERNAME = \"$UI_USERNAME\"/g" /app.py
    sed -i "s/PASSWORD = \"\"/PASSWORD = \"$UI_PASSWORD\"/g" /app.py
fi


#cd /app
#exec python app.py

set -e

mkdir -p /share/aceWebPlayer
#cd /app
exec python app.py -d /share/aceWebPlayer
