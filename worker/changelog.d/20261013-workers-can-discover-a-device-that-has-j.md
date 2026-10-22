---
kind: added
title: Workers can discover a device that has just fetched its ZTP bootstrap
audience: admin
refs: #314
---
The new job type `acex.ztp.discover` logs in to the device with the bootstrap login set on its ZTP method, using the NED chosen for that method, and reports serial number, vendor, hardware model, OS and OS version. The job fails with a clear message if the method has no NED chosen or no bootstrap username and password.
