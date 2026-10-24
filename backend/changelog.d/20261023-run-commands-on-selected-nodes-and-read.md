---
kind: added
title: Run commands and ping on nodes, and read each node's response
---
Runs order an operation on a list of nodes, one job per node. `POST /api/v1/operations/execute` runs raw commands; `POST /api/v1/operations/actions/ping` pings with the same params on every vendor (target, count 1–100, timeout, VRF, source interface, size 36–9216 with don't-fragment). Only nodes whose driver supports the operation are accepted. `GET /api/v1/operations/runs` lists runs, `GET /api/v1/operations/runs/{id}` gives each node's response sorted by hostname, and `/report?format=csv|json` downloads it. Failed jobs are not retried. Drivers now report what they support under `capabilities` in `/api/v1/neds`. Runs need RabbitMQ and a worker; the new `acex.operations` queue is declared on its own, but running workers must be restarted to consume it.
