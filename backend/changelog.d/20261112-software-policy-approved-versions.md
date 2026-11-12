---
kind: added
title: Approve the software versions a vendor or hardware model may run
audience: admin
refs: #368
---
Under `/api/v1/policies/software` an administrator approves software versions per vendor, or per hardware model, whose versions beat its vendor's, and marks at most one of them golden for each operating system, the version to aim for. An asset is measured only against the versions approved for the operating system it runs, and a version that is not approved is not allowed. `GET /api/v1/policies/software/versions` suggests the versions the inventory already runs.

An asset whose model and vendor have no approved version has no policy and is left out of the software percentage. The new migration only adds a table.
