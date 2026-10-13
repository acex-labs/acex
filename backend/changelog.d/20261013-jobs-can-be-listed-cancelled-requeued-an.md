---
kind: added
title: Jobs can be listed, cancelled, requeued and deleted through the API
audience: developer
refs: #312
---
A new `/api/v1/workers` API lists jobs (filter by state, type or subject), shows one job with its result or error, and lets you cancel, requeue a failed or cancelled job, delete one, or purge them by state. It also tells a starting worker which broker and queues to use.
