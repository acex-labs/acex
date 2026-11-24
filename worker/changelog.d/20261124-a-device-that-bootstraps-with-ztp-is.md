---
kind: fixed
title: A device that bootstraps with ZTP is discovered and provisioned again
audience: admin
---
Since the drivers moved to the new interface, a `ztp.discover` or `ztp.provision` job failed as soon as the worker reached the driver, so no device that fetched its bootstrap was ever discovered. The worker now logs in with the ZTP method's bootstrap login through the driver's session, reads the facts the device reports and pushes the node's configuration the same way. The device is told where to fetch its bootstrap before it has applied it, so a device that does not answer yet, or does not take the login yet, is tried again with growing pauses for up to ten minutes before the job fails. The result of a provisioning job now counts the lines that were sent and shows what the device answered, with secrets masked.
