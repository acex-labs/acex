---
kind: internal
title: The image installs its packages from a lock file on a pinned base image
---
The image installs the main dependencies from the committed `poetry.lock`, so a build no longer picks up newer versions and the test packages are no longer in the image, and starts from a Python base image pinned by digest. `poetry lock` in the agent directory refreshes the lock. See the guide on repeatable image builds.
