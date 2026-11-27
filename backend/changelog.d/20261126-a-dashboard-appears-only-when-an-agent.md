---
kind: changed
title: A dashboard appears only when an agent measures what it shows
---
The generated Grafana dashboards were all offered whether anything measured what they show or not, so a board such as ICMP Ping Overview could sit in Grafana and in Observability > Dashboards with every panel saying "No data". A dashboard is now offered only when a telemetry agent is granted the capability it shows (`icmp` for ICMP Ping Overview, `snmp` for SNMP Overview) and there are nodes with a management address to measure. `GET /api/v1/observability/grafana/dashboards` lists only those, and grafana-sync removes a dashboard from its folder at the next sync when it is no longer listed, for example when the last agent with the capability loses it. Give an agent the capability and the dashboard appears by itself.
