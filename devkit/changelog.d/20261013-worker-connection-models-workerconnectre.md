---
kind: added
title: Worker connection models: WorkerConnectRequest and WorkerConnection
audience: developer
refs: #312
---
New module `acex_devkit.models.worker`. A starting worker sends `WorkerConnectRequest(job_types=[...])` and gets a `WorkerConnection` with the `broker` (`BrokerConnection`: `host`, `port`, `vhost`, `user`, `password`) and the `queues` (`QueueDeclaration`: `name`, `durable`) to declare. `JobTypeInfo` pairs a job type `name` with its `queue`.
