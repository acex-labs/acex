---
kind: added
title: Workers run the steps of workflow runs
---
Workers take `acex.operations.workflow.*` jobs from the `acex.operations` queue:

- Execute and action steps render their templates for each node from earlier artifacts, then run like the bulk
  operations.
- Probe steps ping from the worker itself, without privileges. This needs `icmplib`, a new dependency of the
  worker.
- Compute, assert and condition steps read earlier artifacts without logging in anywhere.

Every step computes the artifacts it names over its own result. In a dry run no device is reached. Restart
workers so they register the new job types.
