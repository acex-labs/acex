---
kind: added
title: Search assets from one box
---
`GET /api/v1/inventory/assets?q=<text>` finds assets whose serial number, hardware model, vendor or driver (NED id) contains the text, ignoring case. It combines with the existing filters, such as `assigned=false`, and `total` counts only the assets that match.
