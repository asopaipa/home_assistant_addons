#!/bin/bash

if [ -f "$CONFIG_FILE" ]; then
    UI_USERNAME=$(jq -r '.UI_USERNAME // "user"' "$CONFIG_FILE")
    UI_PASSWORD=$(jq -r '.UI_PASSWORD // "user"' "$CONFIG_FILE")
    ACESTREAM_PORT=$(jq -r '.ACESTREAM_PORT // "6878"' "$CONFIG_FILE")
else
    echo "No se encontró $CONFIG_FILE, usando valores por defecto."
    UI_USERNAME="user"
    UI_PASSWORD="user"
    ACESTREAM_PORT="6878"
fi


# Exportar la variable de entorno para el puerto
export PORTACE=$ACESTREAM_PORT


if [ -n "$ACESTREAM_PORT" ]; then
    sed -i "s/6878/$ACESTREAM_PORT/g" ./app/static/js/main.js
    sed -i "s/6878/$ACESTREAM_PORT/g" ./app/getLinks.py
fi

if [ -n "$UI_USERNAME" ]; then
    sed -i "s/USERNAME = \"\"/USERNAME = \"$UI_USERNAME\"/g" ./app/app.py
    sed -i "s/PASSWORD = \"\"/PASSWORD = \"$UI_PASSWORD\"/g" ./app/app.py
fi


exec python /app/app.py
