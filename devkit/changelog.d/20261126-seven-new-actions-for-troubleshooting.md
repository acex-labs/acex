---
kind: added
title: Seven new actions for troubleshooting from a device
audience: developer
---
`ACTIONS` gains `get_mac_address_table`, `lookup_mac_address`,
`get_ip_route`, `get_arp_table`, `lookup_arp`, `traceroute` and
`get_interface_status`, each with its params and result model and an
optional method of the same name on `Actions`. Their shared conventions:
interface names as the device writes them, MAC addresses as
`aa:bb:cc:dd:ee:ff` (the `MacAddress` type reads any common form), a VRF of
None for the global table, and ages in seconds. A table action's params take
`max_entries`; drivers return every row, and `Session.run_action(params)`,
which replaces `Session.ping`, cuts the table and fills in `total` and
`truncated`.
`ActionSpec` gains a `label` for user interfaces and the `rows`, `columns` and
`fields` of its result; `ActionInfo.of(spec)` is an action as the API lists it.
A workflow action step's result fields are now its own action's, not ping's.
