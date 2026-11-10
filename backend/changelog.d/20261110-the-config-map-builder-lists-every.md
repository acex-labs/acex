---
kind: fixed
title: The config map builder lists every attribute of a component
---
Optional attributes, such as the VLAN ID and the VLAN name of a VLAN, were missing from the builder in the container images, so a component could only be given its required attributes there. The builder now lists all of them.
