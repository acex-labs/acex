---
kind: added
title: Ping from Cisco IOS devices
---
The driver runs the ping action: `ping [vrf X] target repeat N [size S df-bit] timeout T [source IF]`, reporting packets sent and received and round-trip times. A ping the device refuses, e.g. to an unknown host, fails with the device's reason.
