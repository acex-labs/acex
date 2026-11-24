---
kind: fixed
title: A configuration with spanning tree components validates after a JSON round trip
---

A configuration composed from `SpanningTreeGlobal`, `SpanningTreeRSTP`, `SpanningTreeMSTP`, `SpanningTreeMstpInstance` or `SpanningTreeRapidPVST` components failed validation when it was read back from JSON, for example `stp.config.loop_guard: Input should be a valid dictionary`. The model typed `stp.config`, `stp.rstp.config` and `stp.mstp.config` as collections keyed by name, while the configuration engine places one object there, which is also what the API returns. They are now typed as one object each. The MST instances and the Rapid PVST VLANs are collections, and they now start out empty, so that each component is placed under its name; before, only the last of several instances or VLANs was kept. A configuration saved with `stp.config` as a collection keyed by name is no longer accepted.
