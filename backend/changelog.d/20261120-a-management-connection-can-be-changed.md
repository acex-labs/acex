---
kind: fixed
title: A management connection can be changed, so Set primary works
---
`PATCH /api/v1/inventory/management_connections/{id}` now exists. Before, the API had no such route and answered 405, so Set primary on a node's Management Connections card did nothing and showed no message, and `client.inventory.management_connections.update(...)` failed the same way. Send only the fields to change: `primary`, `connection_type` or `target_ip`. A field left out or sent as `null` keeps its value. Making a connection primary makes the node's other connections non-primary. A connection that does not exist answers 404.
