---
kind: removed
title: The old compliance and health endpoints are removed
audience: developer
refs: #368
---
`GET /api/v1/operations/compliance/{node_instance_id}`, `GET /api/v1/operations/compliance/site/{site_name}`, `GET /api/v1/health/node_instance/{node_instance_id}` and `GET /api/v1/health/site/{site_name}` no longer exist. Use `/api/v1/compliance/nodes/{id}` and `/api/v1/compliance/sites/{name}`. The figures are now under `configuration`, next to a `software` section, and a node that has not been collected is `not_collected` instead of missing.

The web interface is changed to match. Anything else that calls the old paths has to be changed before the upgrade.
