---
kind: added
title: The driver and bootstrap login for each ZTP method can be set in the API
audience: admin
refs: #314
---
`GET /api/v1/ztp_methods` lists the ZTP methods; `PUT /api/v1/ztp_methods/{method}` sets which driver discovery uses and the temporary bootstrap username and password. A driver that is not installed in the backend is refused with 422.
