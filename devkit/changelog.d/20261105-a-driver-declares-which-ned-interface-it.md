---
kind: added
title: A driver declares which NED interface it implements
audience: developer
---
A driver inherits `interface_version` from `NetworkElementDriver`; its value is `acex_devkit.drivers.NED_INTERFACE`, which is raised only when the contract between a driver and the process that runs it changes in a way that breaks either side. `Ned`, the entry in the list of drivers, carries it as `interface_version`, and it is `None` when the backend does not say.
