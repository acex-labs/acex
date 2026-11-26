---
kind: added
title: One list of actions that the API, client and MCP tools are made from
audience: developer
---
`acex_devkit.models.actions.ACTIONS` maps each action's name to an
`ActionSpec`: its params model, its result model and `max_wait`, the longest
a caller should wait for one node's answer. The backend's
`/operations/actions/<name>` routes, `client.operations.actions.run()` and
the MCP server's action tools are all built from it. A new action needs its
models and an entry here, plus its driver implementations and the worker's
handler. `PingParams` now documents its action and fields, which is what an
API reader or a language model sees of them.
