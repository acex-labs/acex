FROM python:3.13-slim

RUN pip install --no-cache-dir asyncssh

WORKDIR /app
COPY server.py .

RUN mkdir -p /configs /etc/ssh

EXPOSE 22

CMD ["python", "server.py"]
