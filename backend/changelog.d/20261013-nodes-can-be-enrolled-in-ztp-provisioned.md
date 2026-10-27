---
kind: added
title: Nodes can be enrolled in ZTP, provisioned and cancelled from a pipeline view
refs: #314
---
`/api/v1/ztp_nodes` shows each ZTP node's stage (awaiting device, awaiting approval, ready, provisioning, failed) with stalled ones first, plus a summary count. A ready node can be provisioned, which queues a job for a worker; a node can also be cancelled back to its earlier status or reset to enrolled.
