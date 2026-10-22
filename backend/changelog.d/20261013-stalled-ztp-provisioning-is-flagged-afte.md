---
kind: added
title: Stalled ZTP provisioning is flagged after a configurable time
audience: admin
refs: #314
---
A provisioning job that nobody picks up for 10 minutes, or that runs for more than 30 minutes without finishing, is shown as stalled in the ZTP pipeline. Both limits are settings in the `ztp` section (`provision_queue_timeout_minutes`, `provision_run_timeout_minutes`).
