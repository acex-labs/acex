---
kind: changed
title: `provision_status` has a new value, `enrolled`, for devices in zero-touch setup
breaking: true
refs: #314
---
The `provision_status` values accepted by `find_nodes` and returned by `find_nodes` and `get_node` are now unprovisioned, adopted, enrolled, provisioning, provisioned and failed. `enrolled` replaces `pending` and `bootstrapping`, so filters using those two must change.
