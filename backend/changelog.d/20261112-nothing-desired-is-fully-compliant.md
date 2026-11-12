---
kind: changed
title: A node with nothing desired is fully compliant
refs: #368
---
A node whose desired configuration is empty used to have no compliance percentage. It now reads 100 %, since nothing it should have is missing. A node whose configuration has not been collected still has no percentage.
