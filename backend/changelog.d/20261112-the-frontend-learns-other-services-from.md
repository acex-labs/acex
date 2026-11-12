---
kind: added
title: The web interface learns which other services exist from the backend
audience: admin
---
`GET /api/v1/services` lists the other backends this deployment has and where
they are, for the web interface to call directly. Set
`ACEX_SERVICES_SAMRUAI_URL` to the SamruAI backend to show SamruAI in the web
interface. Left unset, it stays hidden.
