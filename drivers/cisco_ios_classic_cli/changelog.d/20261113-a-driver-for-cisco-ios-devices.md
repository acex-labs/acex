---
kind: added
title: A driver for Cisco IOS devices
refs: #380
---
Devices that run classic IOS, `cisco_ios` in the inventory, have a driver of their own, Cisco IOS (classic) CLI, next to the IOS-XE driver, which is unchanged. It reads configuration that IOS prints in its own way instead of leaving it as unparsed lines: ACL entries without sequence numbers, `access-list` lines with a number, `spanning-tree portfast edge`, `ip device tracking`, and the AAA lines `aaa authorization config-commands` and `console` and `aaa accounting send stop-record` and `update newinfo`. On the IOS configurations we have measured, 57 % of the lines are read, against 41 % with the IOS-XE driver.

An asset uses the driver when its driver (NED id) is set to `CiscoIOSClassicCLIDriver`. What the driver writes to an IOS device has not been tried on a real device yet.
