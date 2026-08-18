from acex import AutomationEngine

from acex.plugins.integrations.netbox import Netbox
from acex.plugins.integrations.netbox_mock import Netbox as Mock
from acex.database import Connection
import os

# Database (Postgres)
db = Connection(
    dbname="ace",
    user="postgres",
    password="",
    host="localhost",
    backend="postgresql"
)


# # External datasources
netbox = Mock(
    url="https://netbox.ngninfra.net/",
    token=os.getenv("NETBOX_TOKEN"),
    verify_ssl=False,
)

ae = AutomationEngine(
    db_connection=db,
    # assets_plugin=netbox,
    # logical_nodes_plugin=netbox,
)


ae.add_integration("ipam", netbox)
ae.add_configmap_dir("config_maps")


# AI OPS
# Named providers + per-task failover chains. The frontend lists providers and
# models via GET /ai_ops/providers and can override the model per request.
# Everything below can also be configured via ACEX_AI_* env vars
# (see docs/examples/ai_ops.md).
ae.ai_ops(
    enabled=True,
    providers=[
        {
            "name": "bergetai",
            "base_url": os.getenv("ACEX_AI_API_BASEURL"),
            "api_key": os.getenv("ACEX_AI_API_KEY"),
        },
        # Optional secondary provider — used as failover and/or for other tasks:
        # {
        #     "name": "local",
        #     "base_url": "http://localhost:11434/v1",
        #     "api_key": "ollama",
        #     "static_models": ["qwen3:32b"],  # when the provider has no /models endpoint
        # },
    ],
    chains={
        # Ordered failover: first level is the default shown in the frontend,
        # subsequent levels are tried if the previous one is unreachable (5xx/timeout).
        "default": ["bergetai/moonshotai/Kimi-K3"],
        # Tasks without an explicit chain inherit "default". Example override:
        # "analysis": ["groq/deepseek-r1", "local/qwen3:32b"],
    },
    mcp_server_url="http://localhost:8000/mcp",
)


# CORS
ae.add_cors_allowed_origin("*")

# Encryption key for device credentials
# ae.set_encryption_key(os.getenv("ACEX_ENCRYPTION_KEY", ""))
ae.set_encryption_key("9VfRDg1KSH4U6-Kv5dG7e59f1iKeGEQHWUAKPnZO4hk=")

# Create the api app!
app = ae.create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
    )
