---
kind: changed
title: Driver packages for workers are built from the installed code at startup
audience: admin
refs: #312
---
The backend now packages each installed driver into a temporary directory when it starts, so the wheel always matches the code that runs; the `packages/neds/` folder in the working directory is no longer created or used. Downloads from the drivers API serve only these wheels.
