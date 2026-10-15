---
kind: fixed
title: Agent can read definitions from an ACEX that requires sign-in
audience: admin
refs: #260, 70c130b
---
Requests to the ACEX API are now sent with the agent's access token. Before, they went out without a token and were refused (HTTP 401), so nothing was synced to Grafana when ACEX required sign-in.
