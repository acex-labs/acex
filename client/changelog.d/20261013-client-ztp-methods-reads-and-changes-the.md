---
kind: added
title: `client.ztp_methods` reads and changes the settings of each ZTP method
audience: developer
refs: #314
---
`ztp_methods.query()` lists the ZTP methods, `get(method)` returns the chosen `ned` and bootstrap login for one, and `update(method, payload)` changes them; fields left out keep their value. An unknown NED raises `AcexValidationError`.
