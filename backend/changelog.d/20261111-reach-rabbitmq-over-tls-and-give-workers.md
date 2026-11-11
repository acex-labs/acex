---
kind: added
title: Reach RabbitMQ over TLS, and give workers their own broker address
audience: admin
---
The backend can now connect to RabbitMQ over TLS. Set `ACEX_RABBITMQ_TLS=true` and it uses `amqps://`, always
verifying the broker's certificate: against the system's trusted roots, or against a CA bundle in
`ACEX_RABBITMQ_TLS_CA_FILE`. A broker that requires a client certificate (mutual TLS) gets
`ACEX_RABBITMQ_TLS_CERT_FILE` and `ACEX_RABBITMQ_TLS_KEY_FILE`, which must be set together. The default is unchanged:
plain `amqp://`.

Workers no longer have to reach the broker the way the backend does. `ACEX_RABBITMQ_WORKER_HOST`,
`ACEX_RABBITMQ_WORKER_PORT` and `ACEX_RABBITMQ_WORKER_TLS` set what `POST /api/v1/workers/connect` hands out. The
backend can stay on the plain port inside the cluster while a worker in a customer's network connects through a TLS
endpoint. Unset, workers are handed the backend's own host, port and TLS setting, as before.
