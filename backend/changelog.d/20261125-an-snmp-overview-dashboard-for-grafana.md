---
kind: added
title: An SNMP overview dashboard for Grafana
---
The Grafana dashboards that ACEX generates now include ACEX — SNMP Overview: how many nodes answered in the last five minutes and the last day, the shortest and longest uptime, uptime for each node and over time (a drop is a restart), and a timeline that shows when a node was not polled. It appears once a telemetry agent is granted the SNMP capability and there are nodes to poll, and grafana-sync puts it in Grafana like the ICMP dashboard. Filter on site and node at the top.
