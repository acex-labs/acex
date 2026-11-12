---
kind: fixed
title: Paging through the node list returns every node once
refs: #370
---
Without a chosen sort the node list now follows the node id, so walking through its pages no longer repeats some nodes and skips others.
