FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    snmpd \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir asyncssh

WORKDIR /app
COPY server.py .
COPY snmpd.conf /etc/snmp/snmpd.conf
COPY entrypoint.sh /entrypoint.sh

RUN mkdir -p /configs /etc/ssh && chmod +x /entrypoint.sh

EXPOSE 22 161/udp

ENTRYPOINT ["/entrypoint.sh"]
