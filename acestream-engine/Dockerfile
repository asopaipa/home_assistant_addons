FROM futebas/acestream-engine-arm:3.2.7.6
RUN apk add --no-cache bash
RUN apk add --no-cache jq

# Etiquetas para Home Assistant
LABEL io.hass.version="1.0.0" io.hass.type="addon" io.hass.arch="armhf|armv7|aarch64"

# Copiar script de ejecución
COPY run.sh /
RUN chmod a+x /run.sh

# Configurar entrypoint
ENTRYPOINT ["/run.sh"]
