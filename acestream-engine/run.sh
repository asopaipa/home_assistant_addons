#!/usr/bin/env bash

CONFIG_FILE="/data/options.json"

if [ -f "$CONFIG_FILE" ]; then
    EXTRA_ARGUMENTS=$(jq -r '.EXTRA_ARGUMENTS // ""' "$CONFIG_FILE")
else
    echo "No se encontró $CONFIG_FILE, usando valor por defecto."
    EXTRA_ARGUMENTS=""
fi

echo "Extra arguments: $EXTRA_ARGUMENTS"



# Construir comandos con parámetros originales y personalizados
COMMAND_ARGS="--client-console --live-cache-type memory --live-mem-cache-size 104857600 --disable-sentry --log-stdout"

# Añadir nuestros parámetros personalizados
COMMAND_ARGS="$COMMAND_ARGS ${EXTRA_ARGUMENTS} "


# Ejecutar el comando
cd /acestream
exec /acestream/python/bin/python ./main.py $COMMAND_ARGS
