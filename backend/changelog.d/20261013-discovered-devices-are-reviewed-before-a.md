---
kind: added
title: Discovered devices are reviewed before an asset is created or updated
refs: #314
---
Each discovery lists what approving it would do (create the asset with that serial, update it, leave it, or blocked and why) and any conflicts such as the same serial on another address. Discoveries can be approved or rejected one by one or in bulk, with a dry run, under `/api/v1/ztp_discoveries`. Approving never changes a node.
