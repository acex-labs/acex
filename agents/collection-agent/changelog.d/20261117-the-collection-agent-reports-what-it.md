---
kind: added
title: The collection agent reports what it found for each node
---
After each round the agent sends the result for every node it tried to ACEX, with a category (`unreachable`, `authentication_failed`, `privilege_failed`, `ssh_algorithm`, `driver_unavailable`, `no_management_ip`, `no_credentials`, `empty_configuration` or `other`) and the start of the message for a node that failed. Against a backend without the route it logs a warning and carries on.
