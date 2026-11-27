---
kind: changed
title: get_running_config reads the configuration from the device now
---
`get_running_config` used to say that ACEX could not read a device live and
point to the newest snapshot. It now reads the running configuration from the
device, with secrets masked, as an action recorded under Operations ›
Standard Actions. The glossary describes how to troubleshoot: test a
hypothesis, looking at the LLDP topology around the node where it has been
collected, then live state from the action tools, then the latest
observed configuration and its drift from desired, and read the running
configuration when the device may have changed since that snapshot.
