---
kind: added
title: Worker installs and upgrades NED drivers itself from the backend
audience: admin
refs: #314
---
NEDs are not part of the worker image. At startup the worker downloads every NED the backend publishes that is missing or at another version and pip-installs it, so it needs access to a package index for their dependencies. If a NED is upgraded after it was already loaded, the worker shuts down gracefully (running jobs finish) and the job fails, so run workers under something that restarts them.
