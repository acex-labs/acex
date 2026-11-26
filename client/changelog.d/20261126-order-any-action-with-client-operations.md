---
kind: added
title: Order any action with client.operations.actions.run
audience: developer
---
`client.operations.actions.run("ping", node_ids, target=...)` orders any
action in devkit's `ACTIONS`, checking its params before sending.
`client.operations.actions.ping(...)` is now a shortcut for it.
