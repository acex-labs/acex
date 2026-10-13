---
kind: added
title: Job outcomes and redeliveries are handled and reported to the backend
audience: admin
refs: #312, #314
---
A worker claims a job before running it and reports success or failure with a message; a handler error, or a result the backend rejects, shows up as a failed job and in the worker log. A message is acknowledged only after its job has run, so a worker that dies mid-job leaves it to be redelivered, and jobs already finished or cancelled are skipped. Jobs run in threads and the number running in parallel is not configurable by `ACEX_*` settings; scale by running more workers.
