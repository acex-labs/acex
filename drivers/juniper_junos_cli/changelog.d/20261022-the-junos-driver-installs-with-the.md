---
kind: fixed
title: The Junos driver installs with the jinja2 it needs
---
The driver imports jinja2 but did not list it, so a collection agent that installed the driver at runtime in a container without jinja2 failed to load it, and the agent then collected nothing from any device. The driver now declares jinja2 like the Cisco driver does.
