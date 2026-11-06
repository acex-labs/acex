---
kind: added
title: A client can refuse a driver of a NED interface it cannot run
audience: developer
---
`Acex(..., ned_interfaces=[2])` names the NED interfaces the process can run. `neds.get_missing()` leaves out a driver that declares another interface and `neds.incompatible` says why. `neds.install()` raises `AcexNedIncompatibleError` (an `AcexNedInstallError`), before anything is downloaded, for a driver the API publishes as another interface. `neds.get_driver_instance()` returns `None` for an installed driver the process cannot use, because it declares another interface or its code cannot be loaded, and `neds.load()` raises `AcexNedIncompatibleError` for all of these instead. A driver that does not declare an interface is not refused, and without `ned_interfaces` nothing is refused, as before.
