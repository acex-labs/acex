---
title: Background jobs on separate workers
status: in_progress
components: acex, acex-worker, acex-frontend
---
Long-running work such as discovery and provisioning is handed to separate
workers through RabbitMQ, and the Activity > Jobs page lists the jobs and lets
you requeue or cancel them.
