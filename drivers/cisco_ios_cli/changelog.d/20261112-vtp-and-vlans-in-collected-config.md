---
kind: added
title: Collected Cisco configurations include VTP settings and VLANs
refs: #365, #366
---
When the driver collects a running configuration it also runs `show vtp status` and `show vlan brief` and adds the VTP domain, mode and version and each VLAN's number and name to the configuration it stores, so that compliance can see them. A command that fails is logged and the configuration is stored without those lines.
