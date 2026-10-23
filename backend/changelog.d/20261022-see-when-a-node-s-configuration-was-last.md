---
kind: added
title: See when a node's configuration was last collected
---
The observed configuration of a node now says when the collection agent last polled the node, in a new `last_collected_at` field next to `created_at`. Until now ACEX only kept the time of the last change, so a node that had not changed for days looked the same as one that was never polled. `GET .../configuration/observed/latest`, `GET .../configuration/observed/{config_id}` and the list of observed configurations return it. A configuration stored before this release has no value until the node is polled again, which happens at the next collection.
