---
kind: added
title: `client.workers` lets a worker connect and process jobs
audience: developer
refs: #312, #314
---
`workers.connect(payload)` returns the broker and queues for the job types a worker runs, and `workers.job_types()` lists every job type and its queue. `workers.jobs` has `query()`, `get(job_id)`, `claim(job_id)`, `succeed(job_id, result)`, `fail(job_id, error)` and `report(job_id, payload)`.
