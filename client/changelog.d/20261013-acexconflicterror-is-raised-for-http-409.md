---
kind: added
title: `AcexConflictError` is raised for HTTP 409 responses
audience: developer
refs: #314
---
A request that does not fit the resource's current state, such as claiming a job that was already taken, now raises `AcexConflictError` (an `AcexHTTPError`) instead of the generic `AcexHTTPError`.
