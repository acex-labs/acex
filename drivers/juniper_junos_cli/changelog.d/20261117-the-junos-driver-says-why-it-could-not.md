---
kind: changed
title: The Junos driver says why it could not connect
---
A refused connection and an SSH negotiation the device does not share are raised as `HostUnreachable` and `SshAlgorithmMismatch` instead of as a timeout, so the collection agent can tell the reasons apart. A real timeout is still `ConnectionTimeout`.
