---
kind: added
title: AI Ops runs on Azure OpenAI and other providers that need more than an API key
audience: admin
breaking: true
---
AI providers are now set up as a connection, a protocol and their models,
so providers that differ from plain OpenAI-compatible servers can be added
with settings alone:

- **Entra ID sign-in**: `AUTH__TYPE=azure_client_secret` with `TENANT_ID`,
  `CLIENT_ID`, `CLIENT_SECRET` and `SCOPE`, instead of `API_KEY`.
- **Responses API**: `API=responses` for OpenAI and Azure reasoning models.
  On those models it is the only protocol that allows tools such as
  neighbour and config lookups.
- **One URL per model**: a `{model}` placeholder in `BASE_URL`, for gateways
  such as Azure API Management.
- **Per-model settings** under `MODELS`: reasoning effort, extra request
  fields, capabilities and cost. Chains can set reasoning effort per task.

A model that refuses tools or a reasoning setting now answers without them,
where it used to fail the request. Errors also reach the chat as a
message instead of cutting the answer off.

**Action needed**: `STATIC_MODELS` and `MODEL_META` are replaced by `MODELS`
(`MODELS=a,b`, or JSON with settings per model). Unknown provider settings
now stop startup with an error instead of being ignored. See
`docs/examples/ai_ops.md`.
