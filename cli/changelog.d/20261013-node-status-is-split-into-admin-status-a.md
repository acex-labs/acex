---
kind: changed
title: Node `status` is split into `admin_status` and `provision_status`
breaking: true
refs: #292
---
`acex node list` no longer has `--status`; use `--admin-status` (planned, active, decommissioned) and `--provision-status` instead. The node table, `acex node show`, and JSON/CSV output now carry `admin_status` and `provision_status` instead of `status`, so scripts that read `status` or pass `--columns status` must be updated. Needs a server that has the same change.
