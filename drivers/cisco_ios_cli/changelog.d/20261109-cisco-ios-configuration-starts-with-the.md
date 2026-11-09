---
kind: fixed
title: Cisco IOS configuration starts with the spanning tree mode
---
The rendered configuration now begins with `spanning-tree mode rapid-pvst` and `spanning-tree extend system-id`, as it did in earlier versions of the driver, so a switch configured from ACEX does not fall back to PVST. A `SpanningTreeGlobal` whose `mode` is `pvst`, `rapid-pvst` or `mst` (`mstp` and `rapid_pvst` are read the same way) is written as that mode instead. The lines are written but not read back from the running configuration.
