---
kind: changed
title: Backend setting `ACEX_AI_MCP_SERVER_URL` is now `ACEX_AI_OPS_MCP_SERVER_URL`
audience: admin
breaking: true
refs: #306
---
Backend settings were renamed to one `ACEX_<SECTION>_<FIELD>` scheme with no aliases for the old names. Where the backend reaches this server, `ACEX_AI_MCP_SERVER_URL` is now `ACEX_AI_OPS_MCP_SERVER_URL`; deployments using the old name must rename it.
