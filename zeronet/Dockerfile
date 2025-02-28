
FROM supersandro2000/zeronet


RUN apk add --no-cache bash
RUN apk add --no-cache jq

# Etiquetas para Home Assistant
LABEL io.hass.version="1.0.0" io.hass.type="addon" io.hass.arch="armhf|armv7|aarch64|amd64"

RUN python3 -m pip install setuptools

RUN mkdir -p /app/log


# Copiar script de ejecución
COPY run.sh /
RUN chmod a+x /run.sh

# Configurar entrypoint
ENTRYPOINT ["/run.sh"]
