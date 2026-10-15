---
title: Nodes have an admin status and a provisioning status
date: 2026-09-30
components: acex 6.23.0, acex-frontend 0.0.34, acex-mcp 1.1.0
---
A node's state is split in two: whether it is meant to be in service (planned, active, decommissioned) and how far provisioning has come. Tables, filters and agent match rules use both.
