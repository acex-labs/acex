---
kind: changed
title: The ZTP script moved to a new URL and needs a bootstrap login to be set
audience: admin
breaking: true
refs: #314
---
The Cisco IOS XE script is now served at `/api/v1/ztp/init_config/cisco_iosxe_python/ztp.py` (it was `.../cisco_iosxe/ztp.py`), and the list at `/api/v1/ztp` is gone. The script uses the bootstrap login set for the method and answers 503 until one is set. Update the URL that devices are pointed at and set the login before devices boot.
