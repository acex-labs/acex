---
kind: changed
title: The agent does not install a driver it cannot run
audience: admin
---
When the backend serves a driver of a NED interface the agent cannot run, for example after the backend was upgraded before the agent, the agent keeps the driver it has, logs the reason once and gives it as the result for every node that needs the driver. Before, the driver was installed and the collection failed on every one of those nodes. Update the agent to run the new interface.
