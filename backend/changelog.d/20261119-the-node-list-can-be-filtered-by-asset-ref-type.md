---
kind: added
title: The node list can be filtered by asset_ref_type
audience: developer
---

`GET /api/v1/inventory/node_instances` takes `asset_ref_type`, `asset` or `asset_cluster`, to use with `asset_ref_id`. A node is bound to either an asset or an asset cluster, and the two have their own numbers, so `asset_ref_id` alone could return a node that belongs to a cluster when an asset had the same number. Without `asset_ref_type` the list answers as before.
