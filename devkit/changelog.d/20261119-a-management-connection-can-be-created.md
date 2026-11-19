---
kind: fixed
audience: developer
title: A management connection can be created with its node
---
`ManagementConnectionCreate` has the field `node_id`, the node the connection belongs to, which the API has always required. Before, the model left it out and dropped it when a body was validated, so `client.inventory.management_connections.create(node_id=..., target_ip=...)` sent a body without it and the API answered 422. `node_id` is required: a call that leaves it out now fails in the client with a validation error instead of a 422 from the API. Nothing changes for code that only reads connections (`ManagementConnectionResponse` already had `node_id`).
