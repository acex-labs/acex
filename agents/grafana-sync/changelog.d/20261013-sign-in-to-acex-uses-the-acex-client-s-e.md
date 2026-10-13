---
kind: changed
title: Sign-in to ACEX uses the ACEX client's environment settings
audience: admin
refs: 70c130b
---
If your ACEX requires sign-in, give the agent client credentials with `ACEX_CLIENT_SECRET`, and if needed `ACEX_CLIENT_ID` and `ACEX_ISSUER_URL`. These are read by the shared ACEX client, not by the agent itself, so check them against your deployment.
