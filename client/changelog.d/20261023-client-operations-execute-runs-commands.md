---
kind: added
title: client.operations runs commands and pings on nodes
audience: developer
---
`client.operations.execute(node_ids, commands)` and `client.operations.actions.ping(node_ids, target=...)` order a run; `client.operations.runs.query()`, `.get(run_id)` and `.report(run_id, format)` read it back.
