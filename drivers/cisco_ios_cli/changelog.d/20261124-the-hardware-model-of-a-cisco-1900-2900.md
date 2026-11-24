---
kind: fixed
title: The hardware model of a Cisco 1900, 2900 or 3900 router is read from the device
---
These routers print their model right after "Cisco" and have no processor on that line (`Cisco CISCO1941/K9 (revision 1.0) with ...`), so the driver reported no hardware model for them. It now reads it, for example `CISCO1941/K9`, together with the serial number, OS and version.
