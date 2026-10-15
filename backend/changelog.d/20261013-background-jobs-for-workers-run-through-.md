---
kind: added
title: Background jobs for workers run through a RabbitMQ broker
audience: admin
refs: #312
---
The backend can now hand work (such as device discovery and provisioning) to separate worker processes through RabbitMQ. Set `ACEX_RABBITMQ_HOST` to switch it on; port, virtual host, user and password are set the same way. Without a host, the job features answer 503 and nothing is queued.
