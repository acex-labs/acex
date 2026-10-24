---
kind: fixed
title: The collection agent collects through the new driver interface
---
Since the drivers moved to the new interface, the agent failed on every device with `'CiscoIOSCLIDriver' object has no attribute 'transport'` and collected nothing. It now opens a session on the driver, reads the configuration and the neighbors through it and uploads them as before. It needs a backend that serves the new drivers (Cisco IOS driver 5 and Junos driver 2).
