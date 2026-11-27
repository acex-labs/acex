---
kind: changed
title: The AI assistant troubleshoots from live state and can read the running config
---
The AI assistant tests a hypothesis step by step: the LLDP topology around the
device where it has been collected, live state such as interface
status, ARP and routes, then the latest observed configuration, compared
with desired when it looks wrong. It reads the running configuration from the
device when you ask for it, or when the device may have changed since the last
snapshot.
