---
kind: added
title: The worker now runs jobs from the message broker the backend names
audience: admin
refs: #312, #314
---
Start it with the `acex-worker` command. At startup it logs in to the ACEX API, asks the backend which broker and queues carry its job types, and consumes from those queues until stopped. It needs a backend that offers this worker connection endpoint and a reachable broker; if login or the connection request fails, it logs `Worker could not start` and exits with an error.
