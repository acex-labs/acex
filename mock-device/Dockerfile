FROM python:3.13-slim@sha256:d0a9e379c0c588befb0e427db17ca9731751d281f32c6cb1a90a1277b680bdad

RUN apt-get update && apt-get install -y --no-install-recommends \
    snmpd \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir asyncssh

WORKDIR /app
COPY server.py show_version.txt ./
COPY snmpd.conf /etc/snmp/snmpd.conf
COPY entrypoint.sh /entrypoint.sh

RUN mkdir -p /configs /etc/ssh && chmod +x /entrypoint.sh

EXPOSE 22 161/udp

ENTRYPOINT ["/entrypoint.sh"]
