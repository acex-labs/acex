---
kind: added
title: Workers run commands and pings on nodes
---
Workers take `acex.operations.execute` and `acex.operations.actions.ping` jobs from the new `acex.operations` queue. They log in with the node's assigned credentials over its management connection. Command output is masked by the node's driver before it is reported; ping reports packets sent and received, round-trip times and success rate. Restart workers to pick up the new queue.
