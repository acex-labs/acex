---
kind: added
title: Runs and batches show when their last job finished
---
`finished_at` on a run in `/api/v1/operations/runs`, and on a batch's parent in `/api/v1/jobs`, is when the last of its jobs finished. It stays empty while any job is queued or running, so a run's duration is `finished_at` minus `created_at`.
