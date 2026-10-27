---
kind: changed
title: Node provision status 'enrolled' replaces 'pending' and 'bootstrapping'
audience: developer
breaking: true
refs: #314
---
A node waiting in ZTP now has the provision status `enrolled`; its stage (awaiting device, awaiting approval, ready) is shown by the ZTP pipeline. The database migration converts existing `pending` and `bootstrapping` nodes and agent match rules. Update scripts or filters that use the old values.
