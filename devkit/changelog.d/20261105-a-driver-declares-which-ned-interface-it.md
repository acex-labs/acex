---
kind: added
title: A driver declares which NED interface it implements
audience: developer
---
A driver sets `interface_version` to a number in its class body: the NED interface it was written for. `acex_devkit.drivers.NED_INTERFACE` is the number devkit defines now, raised only when the contract between a driver and the process that runs it changes in a way that breaks either side, and `NetworkElementDriver.interface_version` is `None` for a driver that does not say, which agents and workers do not check. `Ned`, the entry in the list of drivers, carries the number as `interface_version`, which is `None` where the driver declares none or the backend predates the field.
