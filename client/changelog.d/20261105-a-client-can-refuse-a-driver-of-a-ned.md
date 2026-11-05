---
kind: added
title: A client can refuse a driver of a NED interface it cannot run
audience: developer
---
`Acex(..., ned_interfaces=[2])` names the NED interfaces the process can run. `neds.get_missing()` leaves out a driver of another interface and `neds.incompatible` says why, `neds.install()` and `neds.load()` raise `AcexNedIncompatibleError` (an `AcexNedInstallError`) before anything is downloaded, and `neds.get_driver_instance()` returns `None` for an installed driver it cannot run. A driver that does not say which interface it implements counts as interface 1. Without `ned_interfaces` nothing is refused, as before.
