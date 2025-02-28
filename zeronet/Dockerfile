FROM supersandro2000/zeronet as base
# Se asume que el run.sh original está en la raíz
# (ajusta la ruta si es distinto)

# Etapa final: construimos el addon
FROM supersandro2000/zeronet
# Copiamos el run.sh original de la etapa base a /original_run.sh
COPY --from=base /run.sh /original_run.sh

RUN apk add --no-cache bash
RUN apk add --no-cache jq

# Etiquetas para Home Assistant
LABEL io.hass.version="1.0.0" io.hass.type="addon" io.hass.arch="armhf|armv7|aarch64|amd64"

# Copiar script de ejecución
COPY run.sh /
RUN chmod a+x /run.sh

# Configurar entrypoint
ENTRYPOINT ["/run_home.sh"]
