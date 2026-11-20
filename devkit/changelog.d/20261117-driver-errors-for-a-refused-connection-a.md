---
kind: added
title: Driver errors for a refused connection, a privilege level and an SSH algorithm
---
A driver can raise `HostUnreachable` when no connection could be made (refused, no route), `PrivilegeFailed` when the login works but the privilege level it needs cannot be reached, and `SshAlgorithmMismatch` when the device and the driver share no SSH algorithm. They are connection errors like `AuthenticationFailed` and `ConnectionTimeout`, and the collection agent uses their type to say why a node was not collected.
