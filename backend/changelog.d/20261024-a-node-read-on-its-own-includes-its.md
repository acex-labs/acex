---
kind: fixed
title: A node read on its own includes its management connections
---
`GET /api/v1/inventory/node_instances/{id}` returned an empty `management_connections` list, so workers could not log in to the node, e.g. a ping failed with "has no management connection of type ssh". It now holds the node's connections, primary first, as the node list does.
