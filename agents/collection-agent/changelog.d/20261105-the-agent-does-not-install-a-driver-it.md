---
kind: changed
title: The agent does not install a driver it cannot run
audience: admin
---
When the backend serves a driver that declares a NED interface the agent cannot run, for example after the backend was upgraded before the agent, the agent does not install it and logs the reason once. If the agent already has a driver for that NED it keeps using it. If it has none, every node that needs the NED gets the reason as its result and is tried again every five minutes until the driver is usable, instead of waiting for the next collection; the other nodes are not collected again. A driver whose code cannot be loaded is reported the same way and no longer stops the whole collection. Before, the driver was installed and the collection failed on every one of those nodes. A backend that does not say which interface a driver declares is trusted as before. Update the agent to run the new interface.
