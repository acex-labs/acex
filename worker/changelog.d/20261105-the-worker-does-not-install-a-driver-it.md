---
kind: changed
title: The worker does not install a driver it cannot run
audience: admin
---
A driver that declares a NED interface the worker cannot run is not installed, and the job that needs it fails with the reason, for example to update the worker, instead of failing later inside the driver. A driver whose code cannot be loaded fails its job with the reason too. A backend that does not say which interface a driver declares is trusted as before.
