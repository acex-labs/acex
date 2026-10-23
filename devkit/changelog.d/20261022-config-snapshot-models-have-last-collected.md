---
kind: added
title: Config snapshot models have last_collected_at
audience: developer
---
`ConfigSnapshotDetail` and `ConfigSnapshotListItem` have a new optional field, `last_collected_at`: the last time the node was polled and still had this configuration. It is empty for a configuration stored before the field existed, until the node is polled again.
