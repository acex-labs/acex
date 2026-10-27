---
kind: added
title: Agent acks and responses carry agent_version, build_id and build_ref
audience: developer
---
`CollectionAgentAck` and `TelemetryAgentAck` take the optional fields `agent_version`, `build_id` and `build_ref`, and `CollectionAgentResponse` and `TelemetryAgentResponse` return them. Both default to `None`, so existing agents and clients keep working.
