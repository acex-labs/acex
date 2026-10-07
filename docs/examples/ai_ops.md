# AI Ops — providers, models and failover chains

ACEX AI Ops is configured with **named providers** (OpenAI-compatible endpoints)
and **per-task failover chains** (ordered lists of `provider/model` levels).

- The frontend discovers providers and models via `GET /ai_ops/providers` and
  can refresh a single provider's list via `GET /ai_ops/models?provider=X`.
  Models include metadata when available — `supports_tools`, `supports_vision`,
  `context_window`, `input/output_cost_per_mtok` — harvested from the provider's
  `/models` response (e.g. OpenRouter exposes capabilities and pricing) and
  overridable per model via the provider's `model_meta` config. Fields the
  provider does not report are `null`.
- Both `POST /ai_ops/ai/ask` (task `chat`) and `POST /ai_ops/ai/config_analysis`
  (task `analysis`) accept an optional `model` field. When omitted, the task's
  failover chain is used. An explicit override runs **without failover**.
- Failover happens only *before the first token*: connection errors, timeouts,
  HTTP 429 and 5xx move to the next chain level; 4xx fails immediately
  (configuration problem, not transient).
- Tasks without their own chain inherit `default`.
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
                  "static_models": ["qwen3:32b"],
                  # Declare capabilities yourself when the provider doesn't report them:
                  "model_meta": {"qwen3:32b": {"supports_tools": True, "context_window": 32768}}},
    },
    chains={
        "default":  ["groq/moonshotai/Kimi-K3", "local/qwen3:32b"],
        "analysis": ["groq/deepseek-r1"],
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
ACEX_AI_OPS_PROVIDERS__LOCAL__STATIC_MODELS=qwen3:32b,llama3.3   # optional, if no /models endpoint
ACEX_AI_OPS_PROVIDERS__LOCAL__MODEL_META={"qwen3:32b": {"supports_tools": true, "context_window": 32768}}  # optional JSON

# Chains (comma-separated provider/model levels, in failover order):
ACEX_AI_OPS_CHAINS__DEFAULT="groq/moonshotai/Kimi-K3, local/qwen3:32b"
ACEX_AI_OPS_CHAINS__ANALYSIS="groq/deepseek-r1"

# MCP tool server:
ACEX_AI_OPS_MCP_SERVER_URL=http://localhost:8000/mcp
```

Provider names from the environment are lower-cased (`GROQ` → `groq`).

- A value in code wins over the environment. For `providers` and `chains` the
  two are merged by name, code winning per name.
- A provider without a `default` chain, a chain naming an unknown provider or a
  provider missing `base_url`/`api_key` fails at startup with an actionable error.
- To disable, configure no provider. Tasks without their own chain inherit
  `default`.

The previous layout (`ACEX_AI_PROVIDERS=groq,local`, `ACEX_AI_PROVIDER_<NAME>_BASEURL`,
`ACEX_AI_CHAIN_<TASK>`) is no longer read. `ae.ai_ops(...)` still works but is
deprecated.
