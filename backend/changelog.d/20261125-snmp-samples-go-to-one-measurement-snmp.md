---
kind: changed
audience: admin
title: SNMP samples go to one measurement, snmp, with the node as a tag
---
The SNMP input named its measurement after the node, so every node had a table of its own in InfluxDB and no dashboard could read them together. It now writes the measurement `snmp`, as the ICMP input writes `ping`, and the node is the tag `node`. Samples already written under node names stay where they are and can be removed from InfluxDB; a dashboard or query of your own that reads them has to read `snmp` and filter on the tag `node`. The change reaches the agents when their Telegraf configuration is rendered again.
