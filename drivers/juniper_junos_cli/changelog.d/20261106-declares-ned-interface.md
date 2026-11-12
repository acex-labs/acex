---
kind: internal
title: The driver declares the NED interface it implements
---
The driver sets `interface_version = 2` in its class body. The backend lists that number for it, so an agent or worker that runs another NED interface does not install it. Nothing changes on the devices.
