---
kind: added
title: client.operations.patch renders and applies configuration patches
---
`client.operations.patch.render(node_ids, paths=[...], prune=...)` orders a plan, and `client.operations.patch.apply(plan_id, node_ids)` sends it.
