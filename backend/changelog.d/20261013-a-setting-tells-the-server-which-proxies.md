---
kind: added
title: A setting tells the server which proxies to trust for the client address
audience: admin
refs: #314
---
ZTP identifies a device by the address it fetched its script from, so behind a reverse proxy the server must trust the proxy's forwarded address. Set `forwarded_allow_ips` in the server section to the proxy's address or network; unset, only local connections are trusted.
