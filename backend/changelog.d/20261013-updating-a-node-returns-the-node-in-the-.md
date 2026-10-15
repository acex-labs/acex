---
kind: changed
title: Updating a node returns the node in the same form as reading it
audience: developer
refs: #314
---
The response to a node update now has the same fields as `GET` on that node, so a client can read both the same way.
