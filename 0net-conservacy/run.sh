#!/usr/bin/env bash

CONFIG_FILE="/data/options.json"

if [ -f "$CONFIG_FILE" ]; then
    FLAGS=$(jq -r '.FLAGS // "--ui_ip 0.0.0.0"' "$CONFIG_FILE")
    
else
    echo "No se encontró $CONFIG_FILE, usando valores por defecto."
    FLAGS="--ui_ip 0.0.0.0"

fi


cd /app/ZeroNet
echo "Starting ZeroNet..."
exec python3 zeronet.py $FLAGS  
