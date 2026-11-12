---
kind: added
title: Choose which hardware models the installation runs
audience: admin
refs: #368
---
`GET /api/v1/platforms` lists the vendors and hardware models ACEX knows, the operating systems each runs, which of them an installed driver supports, and which models are enabled. A model is enabled when an asset of it enters the inventory, or with `PUT /api/v1/platforms/enabled_models/{model}`; `DELETE` on the same path disables it. Only enabled models can be named in a software policy.
