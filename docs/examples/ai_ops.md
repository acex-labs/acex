# AI Ops — providers, models and failover chains

AI Ops talks to language models through **named providers**. Each task (`chat`,
`analysis`) has a **failover chain**: an ordered list of `provider/model` levels.

A provider combines three things, and a model can override the first two:

| | What it is | Settings |
|---|---|---|
| **Connection** | where the provider is and how to sign in | `base_url`, `api_key` or `auth` |
| **Protocol** | the wire format the provider speaks | `api`: `chat_completions` (default) or `responses` |
| **Models** | what each model can do and how to call it | `models`: reasoning effort, extra request fields, capabilities, cost |

- `chat_completions` is what OpenAI-compatible servers speak (Groq, Berget,
  OpenRouter, Ollama, vLLM). `responses` is OpenAI's newer API. It is the only
  protocol on which OpenAI and Azure reasoning models accept tools. It also
  keeps the model's reasoning across tool calls.
- The frontend discovers providers and models via `GET /ai_ops/providers` and
  can refresh one provider's list via `GET /ai_ops/models?provider=X`. Model
  metadata (`supports_tools`, `supports_vision`, `context_window`,
  `input/output_cost_per_mtok`) is harvested from the provider's `/models` and
  overridden by what is configured under `models`. Fields nobody reports are
  `null`.
- Both `POST /ai_ops/ai/ask` (task `chat`) and `POST /ai_ops/ai/config_analysis`
  (task `analysis`) accept an optional `model` field. When omitted, the task's
  failover chain is used. An explicit model runs **without failover**.
- Failover happens only *before the first output*: connection errors, timeouts,
  HTTP 429 and 5xx move to the next chain level. Authentication errors and
  invalid requests fail immediately, because they point at the configuration.
- When a model refuses a feature of the request, the same model is asked again
  without that feature. This covers tools, or a reasoning setting it cannot
  combine with tools. Reasoning is turned off first, and the tools are dropped
  only if that is also refused. The result is logged as a warning and
  remembered for that model, so the request still gets an answer. A model
  configured with `supports_tools: false` is never sent tools at all.
- AI Ops needs **no code at all**: it is on as soon as a provider is
  configured in the environment (see below).

## Configuration

Every setting can be given in code or as an environment variable; see
`acex.settings`. In code:

```python
from acex import AutomationEngine
from acex.settings import AIOpsSettings, Settings

ae = AutomationEngine(settings=Settings(ai_ops=AIOpsSettings(
    providers={
        "groq": {"base_url": ..., "api_key": ...},
        "local": {"base_url": "http://localhost:11434/v1", "api_key": "ollama",
                  # Declare models and capabilities when the provider doesn't report them:
                  "models": {"qwen3:32b": {"supports_tools": True, "context_window": 32768}}},
    },
    chains={
        "default":  ["groq/moonshotai/Kimi-K3", "local/qwen3:32b"],
        "analysis": [{"provider": "groq", "model": "deepseek-r1", "reasoning_effort": "high"}],
    },
    mcp_server_url="http://localhost:8000/mcp",
)))
```

The same in the environment. Providers and chains are keyed by name, with `__`
between the levels:

```bash
# Providers, one block per name:
ACEX_AI_OPS_PROVIDERS__GROQ__BASE_URL=https://api.groq.com/openai/v1
ACEX_AI_OPS_PROVIDERS__GROQ__API_KEY=gsk_...
ACEX_AI_OPS_PROVIDERS__LOCAL__BASE_URL=http://localhost:11434/v1
ACEX_AI_OPS_PROVIDERS__LOCAL__API_KEY=ollama
ACEX_AI_OPS_PROVIDERS__LOCAL__MODELS=qwen3:32b,llama3.3          # names only, or JSON with settings:
ACEX_AI_OPS_PROVIDERS__LOCAL__MODELS={"qwen3:32b": {"supports_tools": true, "context_window": 32768}}

# Chains, in failover order: "provider/model,provider/model", or JSON for per-task settings:
ACEX_AI_OPS_CHAINS__DEFAULT="groq/moonshotai/Kimi-K3, local/qwen3:32b"
ACEX_AI_OPS_CHAINS__ANALYSIS='[{"provider": "groq", "model": "deepseek-r1", "reasoning_effort": "high"}]'

# MCP tool server:
ACEX_AI_OPS_MCP_SERVER_URL=http://localhost:8000/mcp
```

Provider names from the environment are lower-cased (`GROQ` → `groq`).

### Model settings

Everything under a model in `models` is optional:

| Field | Meaning |
|---|---|
| `reasoning_effort` | `none`, `low`, `medium`, `high`, … — sent the way the protocol expects it |
| `params` | extra request fields sent as they are, e.g. `{"temperature": 0.2}` |
| `base_url`, `api` | this model's own URL or protocol, instead of the provider's |
| `supports_tools`, `supports_vision`, `context_window` | capabilities, winning over `/models` |
| `input_cost_per_mtok`, `output_cost_per_mtok`, `currency` | cost per million tokens, for the usage shown in chat |
| `extra` | anything else to pass through to the model list |

A chain level can carry `reasoning_effort` and `params` as well. They win over
the model's settings for that task only, so one model can run with low effort
in chat and high effort in the analysis.

A provider that has no `/models` endpoint gets its model list from `models`.
Configured models are listed together with whatever `/models` reports.

### Azure OpenAI with Entra ID (e.g. behind API Management)

Use `auth` instead of `api_key` when the endpoint takes an Entra ID token as
its bearer. ACEX gets the token with a client secret (azure-identity's
`ClientSecretCredential`) and renews it before it expires.

A gateway that gives every model its own URL is one provider whose `base_url`
has a `{model}` placeholder. Such a provider has no single `/models` to list,
so its models must be configured.

```bash
ACEX_AI_OPS_PROVIDERS__APIM__BASE_URL='https://api.example.com/{model}/openai/v1/'
ACEX_AI_OPS_PROVIDERS__APIM__API=responses
ACEX_AI_OPS_PROVIDERS__APIM__MODELS=gpt-6.1,gpt-6.1-mini
ACEX_AI_OPS_PROVIDERS__APIM__AUTH__TYPE=azure_client_secret
ACEX_AI_OPS_PROVIDERS__APIM__AUTH__TENANT_ID=<tenant id>
ACEX_AI_OPS_PROVIDERS__APIM__AUTH__CLIENT_ID=<app registration client id>
ACEX_AI_OPS_PROVIDERS__APIM__AUTH__CLIENT_SECRET=<client secret>
ACEX_AI_OPS_PROVIDERS__APIM__AUTH__SCOPE=https://cognitiveservices.azure.com/.default

ACEX_AI_OPS_CHAINS__DEFAULT="apim/gpt-6.1, apim/gpt-6.1-mini"
```

`SCOPE` is whatever the gateway's token validation expects; ask its owner.
Quote a `base_url` with `{model}` in a shell file so the braces are kept as
they are.

### Startup checks

- A value in code wins over the environment. For `providers` and `chains` the
  two are merged by name, code winning per name.
- Startup fails with an actionable error when:
  - there are providers but no `default` chain,
  - a chain names an unknown provider,
  - a provider is missing `base_url`, or does not have exactly one of `api_key` and `auth`,
  - a `{model}` URL has no configured models,
  - a provider or model setting has an unknown name.
- To disable, configure no provider. Tasks without their own chain inherit
  `default`.

`STATIC_MODELS` and `MODEL_META` are replaced by `MODELS`. The older layout
(`ACEX_AI_PROVIDERS=groq,local`, `ACEX_AI_PROVIDER_<NAME>_BASEURL`,
`ACEX_AI_CHAIN_<TASK>`) is no longer read. `ae.ai_ops(...)` still works but is
deprecated.
