---
kind: internal
title: The image installs pinned packages on a pinned base image
---
The image installs the third-party Python packages at the versions in `backend/constraints.txt`, not at the newest versions of the day, and starts from a Python base image pinned by digest. `scripts/lock-images.sh backend` refreshes the pins. See the guide on repeatable image builds.
