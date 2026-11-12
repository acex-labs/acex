---
kind: added
title: The driver list says which NED interface each driver implements
audience: developer
---
`GET /api/v1/neds` and `GET /api/v1/neds/{ned_id}` return `interface_version` for each driver, the NED interface it declares or `null` when it declares none, so an agent or worker can tell before it installs a driver whether it can run it.
