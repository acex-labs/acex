---
kind: added
title: Cisco IOS devices are read by the Cisco CLI driver
refs: #380
---
The driver now takes devices whose operating system is `cisco_ios`, next to `cisco_iosxe`. Configuration that IOS prints in its own way is read into the node's configuration instead of being left as unparsed lines: ACL entries without sequence numbers, `access-list` lines with a number, `spanning-tree portfast edge`, `ip device tracking`, and the AAA lines `aaa authorization config-commands` and `console` and `aaa accounting send stop-record` and `update newinfo`. On the IOS configurations we have measured, the share of lines that is read went from 41 % to 57 %.

What the driver writes to an IOS device has not been tried on a real device yet.
