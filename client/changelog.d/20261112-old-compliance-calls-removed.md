---
kind: removed
title: client.operations.compliance and the health calls are removed
audience: developer
refs: #368
---
`client.operations.compliance` and `client.system.health_node` and `health_site` are gone, as the endpoints behind them. Use `client.compliance.node(id)` and `client.compliance.site(name)`; the configuration figures are under `configuration`.
