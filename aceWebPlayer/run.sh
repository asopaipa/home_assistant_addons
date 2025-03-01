#!/bin/bash

if [ -f "$CONFIG_FILE" ]; then
    ENABLE_TOR=$(jq -r '.ENABLE_TOR // "false"' "$CONFIG_FILE")
    UI_PASSWORD=$(jq -r '.UI_PASSWORD // ""' "$CONFIG_FILE")
else
    echo "No se encontró $CONFIG_FILE, usando valores por defecto."
    ENABLE_TOR="false"
    UI_PASSWORD=""
fi


# Pedir el puerto al usuario
read -p "¿En qué puerto quieres que se publique la web? (5001) " PORT

read -p "¿En qué puerto quieres que se publique el Acestream? (6878) " PORTACE



# Preguntar si se quiere permitir el acceso remoto
read -p "Si quieres proteger la web con usuario y contraseña, introduce el usuario: " USUARIO

if [ -n "$USUARIO" ]; then
    read -p "Introduce la contraseña: " CONTRASENYA
fi

# Exportar la variable de entorno para el puerto
export PORT=$PORT
export PORTACE=$PORTACE


if [ -n "$PORTACE" ]; then
    sed -i "s/6878/$PORTACE/g" ./static/js/main.js
    sed -i "s/6878/$PORTACE/g" ./getLinks.py
fi

if [ -n "$USUARIO" ]; then
    sed -i "s/USERNAME = \"\"/USERNAME = \"$USUARIO\"/g" app.py
    sed -i "s/PASSWORD = \"\"/PASSWORD = \"$CONTRASENYA\"/g" app.py
fi


docker build -t acestream-player .
