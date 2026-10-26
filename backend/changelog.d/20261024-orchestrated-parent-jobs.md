---
kind: internal
title: Jobs nest, can be scheduled, and orchestrated parents keep their own state
---
A workflow run is a job with a job per step under it, and a step on nodes holds one job per node. Cancel,
delete and purge reach every level.

A job enqueued with `run_at`, or of a job type the backend runs itself (`local`), is `scheduled`. It is not
queued until a dispatcher loop in the API finds it due. The loop takes due jobs with `SKIP LOCKED`, so several
API processes can run it at once. The migration adds `job.run_at` and the job states `paused` and `scheduled`.
