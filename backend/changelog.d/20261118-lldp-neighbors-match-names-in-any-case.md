---
kind: fixed
title: LLDP neighbors are matched to nodes whatever case the device reports its name in
---

A neighbor that reported its name in another case than the inventory holds, such as `CORE-SW1` for `core-sw1`, or with spaces around it, was left unresolved, so its link was missing from the topology. It is now matched ignoring case and spaces, with or without the domain. A name that matches exactly still wins. Links that were left unresolved for this reason are filled in the next time the node's neighbors are collected.
