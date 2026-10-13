---
kind: removed
title: The placeholder Worker class, worker.yaml and optional extras are gone
audience: developer
refs: #314, #312
---
The earlier `Worker` Python class (which only printed a message and ran no jobs), the `acex-worker start` form, the `worker.yaml` example and the `celery` extra no longer exist; Celery is now a normal dependency and the Redis dependency was dropped. The package now depends on the ACEX client and devkit instead of the backend package, and `acex_worker.__version__` is no longer defined.
