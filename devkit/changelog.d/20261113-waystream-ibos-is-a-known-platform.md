---
kind: added
audience: developer
title: Waystream iBOS is a known platform
---
New `Vendor.waystream` and `OS.waystream_ibos`, with a version scheme (`WaystreamIbosVersions`) that accepts what `show version` prints, for example `6.3.5-ED-R`, `7.6.2-GD-R` and `6.1.0-ED-RC2`. Versions compare by their numbers and the release class (ED, GD); the suffix after it (R, RC2) is accepted but not compared. No device types are declared yet, so no Waystream hardware appears in the platform catalog until a model is added.
