---
kind: changed
title: The Cisco IOS-XE driver says why it could not connect
---
A refused connection, a privilege level that could not be reached and an SSH algorithm the device does not share are raised as `HostUnreachable`, `PrivilegeFailed` and `SshAlgorithmMismatch` instead of the raw scrapli, asyncssh or socket error, so the collection agent can tell the reasons apart.
