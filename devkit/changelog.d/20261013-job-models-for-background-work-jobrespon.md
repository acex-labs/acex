---
kind: added
title: Job models for background work: JobResponse, JobSummary, JobUpdate
audience: developer
refs: #312
---
New module `acex_devkit.models.job` with `JobState` (`queued`, `running`, `succeeded`, `failed`, `cancelled`), `JobSubjectType`, `JobResponse`, `JobSummary` (listings, without `data`/`result`/`error`), `JobPurge` and `JobUpdate`. `JobUpdate` is what a worker reports; it rejects a `result` unless the state is `succeeded` and a `failed` state without an `error`. These are also the backend API's job payloads.
