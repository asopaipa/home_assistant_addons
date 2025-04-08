# Use Python 3.11 slim image
FROM python:3.11-slim

VOLUME [ "/share" ]

#RUN apt-get update && apt-get -y install jq bash

RUN apt-get update && apt-get install -y jq bash \
    curl \
    wget \
    gnupg \
    ca-certificates \
    unzip \
    git \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    libxshmfence1 \
    libxss1 \
    libxtst6 \
    libjpeg62-turbo \
    libwebp6 \
    libicu67 \
    libwoff1 \
    libenchant-2-2 \
    libopus0 \
    libevent-2.1-7 \
    libffi7 \
    libegl1 \
    libgles2 \
    libevdev2 \
    libharfbuzz-icu0 \
    libhyphen0 \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# Etiquetas para Home Assistant
LABEL io.hass.version="1.0.0" io.hass.type="addon" io.hass.arch="armhf|armv7|aarch64|amd64"

COPY run.sh /

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

# Copy the rest of the application
COPY . .

# Create resources directory if it doesn't exist
RUN mkdir -p resources

# Expose port 5000
EXPOSE 5000

RUN chmod a+x /run.sh

# Configurar entrypoint
ENTRYPOINT ["/run.sh"]
