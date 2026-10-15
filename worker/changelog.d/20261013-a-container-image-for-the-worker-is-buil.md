---
kind: added
title: A container image for the worker is built in the dev pipeline
audience: admin
refs: #315
---
A `Dockerfile` for the worker produces an image named `acex-worker` whose entrypoint is `acex-worker`; set `ACEX_BASE_URL`, `ACEX_CLIENT_ID` and `ACEX_CLIENT_SECRET` in the deployment. For now the image is only built and published by the development pipeline, not a release pipeline.
