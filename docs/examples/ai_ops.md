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

## Configuration in code (app.py)

```python
ae.ai_ops(
    enabled=True,
    providers=[
        {"name": "groq", "base_url": ..., "api_key": ...},
        {"name": "local", "base_url": "http://localhost:11434/v1",
         "api_key": "ollama", "static_models": ["qwen3:32b"],
         # Declare capabilities yourself when the provider doesn't report them:
         "model_meta": {"qwen3:32b": {"supports_tools": True, "context_window": 32768}}},
    ],
    chains={
        "default":  ["groq/moonshotai/Kimi-K3", "local/qwen3:32b"],
        "analysis": ["groq/deepseek-r1"],
    },
    mcp_server_url="http://localhost:8000/mcp",
)
```

## Configuration via environment variables

```bash
# Named providers (comma-separated list, then one block per provider):
ACEX_AI_PROVIDERS=groq,local
ACEX_AI_PROVIDER_GROQ_BASEURL=https://api.groq.com/openai/v1
ACEX_AI_PROVIDER_GROQ_API_KEY=gsk_...
ACEX_AI_PROVIDER_LOCAL_BASEURL=http://localhost:11434/v1
ACEX_AI_PROVIDER_LOCAL_API_KEY=ollama
ACEX_AI_PROVIDER_LOCAL_STATIC_MODELS=qwen3:32b,llama3.3   # optional, if no /models endpoint
ACEX_AI_PROVIDER_LOCAL_MODEL_META={"qwen3:32b": {"supports_tools": true, "context_window": 32768}}  # optional JSON

# Chains (comma-separated provider/model levels, in failover order):
ACEX_AI_CHAIN_DEFAULT="groq/moonshotai/Kimi-K3, local/qwen3:32b"
ACEX_AI_CHAIN_ANALYSIS="groq/deepseek-r1"

# MCP tool server:
ACEX_AI_MCP_SERVER_URL=http://localhost:8000/mcp
```

Code wins over env vars; `ae.ai_ops(enabled=True)` with no arguments reads
everything from the environment. A `default` chain is required — tasks without
their own chain inherit it.
