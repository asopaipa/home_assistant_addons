# Use Python 3.11 slim image
FROM python:3.11-slim

VOLUME [ "/share" ]

RUN apt-get update && apt-get -y install jq bash

# Etiquetas para Home Assistant
LABEL io.hass.version="1.0.0" io.hass.type="addon" io.hass.arch="armhf|armv7|aarch64|amd64"

COPY run.sh /

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create resources directory if it doesn't exist
RUN mkdir -p resources

# Expose port 5000
EXPOSE 5000

RUN chmod a+x /run.sh

# Configurar entrypoint
ENTRYPOINT ["/run.sh"]
