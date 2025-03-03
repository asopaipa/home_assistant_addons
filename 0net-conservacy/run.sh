#!/usr/bin/env bash

CONFIG_FILE="/data/options.json"

if [ -f "$CONFIG_FILE" ]; then
    ENABLE_TOR=$(jq -r '.ENABLE_TOR // "false"' "$CONFIG_FILE")
    UI_PASSWORD=$(jq -r '.UI_PASSWORD // ""' "$CONFIG_FILE")
    TOR_CONTROL_PORT=$(jq -r '.TOR_CONTROL_PORT // "9151"' "$CONFIG_FILE")
    TOR_SOCKS_PORT=$(jq -r '.TOR_SOCKS_PORT // "9150"' "$CONFIG_FILE")
    PORT_FILESERVER=$(jq -r '.ports["26552/tcp"] // 26552' "$CONFIG_FILE")
    UID_PORT=$(jq -r '.ports["43110/tcp"] // 43110' "$CONFIG_FILE")
    TOR_CONTROL_PASSWD=$(jq -r '.TOR_CONTROL_PASSWD // "changeme"' "$CONFIG_FILE")
    
else
    echo "No se encontró $CONFIG_FILE, usando valores por defecto."
    ENABLE_TOR="false"
    UI_PASSWORD=""
    TOR_CONTROL_PORT="9151"
    TOR_SOCKS_PORT="9150"
    PORT_FILESERVER="26552"
    TOR_CONTROL_PASSWD="changeme"
    UID_PORT="43110"
fi

export ENABLE_TOR
export UI_PASSWORD
export TOR_CONTROL_PORT
export TOR_SOCKS_PORT
export TOR_CONTROL_PASSWD
export UID_PORT
export PORT_FILESERVER


# Setup ZeroNet config if not exists
ZERONET_CONFIG="/app/config/zeronet.conf"
if [ ! -f "$ZERONET_CONFIG" ]; then
    echo "Creating default ZeroNet config..."
    cat > "$ZERONET_CONFIG" << EOF
[global]
ui_ip = *
ui_host =
 0.0.0.0
 localhost
ui_port = $UID_PORT
fileserver_port = $PORT_FILESERVER
tor = $ENABLE_TOR
tor_controller = tor:$TOR_CONTROL_PORT
tor_proxy = tor:$TOR_SOCKS_PORT
tor_password = $TOR_CONTROL_PASSWD
ui_password = $UI_PASSWORD
EOF
fi

# Create symlink to config
ln -sf "$ZERONET_CONFIG" /app/ZeroNet/zeronet.conf


cd /app/ZeroNet
echo "Starting ZeroNet..."
exec python3 zeronet.py main  

#--ui_ip "*" --fileserver_port $PORT_FILESERVER \
#--tor $ENABLE_TOR --tor_controller tor:$TOR_CONTROL_PORT \
#--tor_proxy tor:$TOR_SOCKS_PORT --tor_password $TOR_CONTROL_PASSWD --ui_password $UI_PASSWORD
