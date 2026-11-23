---
kind: added
title: Software compliance can be listed asset by asset
audience: developer
---
The assets of every node, each against the software policy, as a page you can filter, search and sort: `GET /api/v1/compliance/software/assets`. Each row has the asset, its running version, the version to aim for, its status, and the node, site and regions it belongs to. Narrow it with `status` (more than once if you like), `site` and `region`, search with `q`, and order it with `sort` and `order`. Without a `sort` the assets that are not on an approved version come first. `status_counts` says how many assets each status has among those the other filters match. It counts the same assets as the compliance of the installation and answers at once however many nodes there are, because it reads the software policy and the inventory and never a node's configuration.
