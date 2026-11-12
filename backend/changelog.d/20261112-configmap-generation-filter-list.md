---
kind: changed
title: ConfigMap generation, reconcile and translate take a list of filters
audience: developer
refs: #369
---
The request bodies of `/api/v1/config_components/generate`, `/reconcile/{node_instance_id}` and `/translate` now have `filter` as a list of filters instead of a single one, and all of them apply together. A client that sends a single filter object has to send a list with one entry.
