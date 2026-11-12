---
kind: added
title: Search the whole inventory from one endpoint
---
`GET /api/v1/search?q=<text>` finds logical nodes, node instances, sites, regions, assets, asset clusters and contacts whose identifying fields contain the text, case-insensitively. A node instance is also found by its management IP or its asset's serial number. Results are grouped per kind with a total and the best hits first (`limit`, default 5). The text needs at least two characters.
