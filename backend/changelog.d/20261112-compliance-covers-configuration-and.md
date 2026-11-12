---
kind: added
title: Compliance covers configuration and software, for nodes, sites and regions
refs: #368
---
`GET /api/v1/compliance` measures every node and sums it up in total, per site and per region. `/api/v1/compliance/nodes/{id}`, `/api/v1/compliance/sites/{name}` and `/api/v1/compliance/regions/{name}` do the same for one node, site or region. Each answer has a configuration section, the desired configuration against the latest collected one, and a software section, what each asset runs against the software policy. The two are separate figures: a node can be fully compliant in its configuration and not in its software.

A node whose configuration has not been collected is listed as not collected and left out of the percentage. Nothing is stored: every call measures the nodes it covers, so the overview takes longer the more nodes there are.
