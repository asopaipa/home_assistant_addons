FROM python:3.12-alpine



RUN apk --update --no-cache --no-progress add git gcc libffi-dev musl-dev make openssl g++ autoconf automake libtool bash jq

RUN adduser -u 1600 -D service-0net

USER service-0net:service-0net

WORKDIR /home/service-0net

COPY requirements.txt .

RUN python3 -m pip install -r requirements.txt

# the part below is updated with source updates

COPY . .

# Copiar script de ejecución
COPY run.sh /
RUN chmod a+x /run.sh

# Configurar entrypoint
ENTRYPOINT ["/run.sh"]
