from acex import AutomationEngine

from acex.plugins.integrations import Sqlite, Netbox
from acex.database import Connection
from acex.settings import Settings
import os

# Database (Postgres)
db = Connection(
    dbname=os.getenv("ACEX_DB_NAME"),
    user=os.getenv("ACEX_DB_USER"),
    password=os.getenv("ACEX_DB_PASSWORD"),
    host=os.getenv("ACEX_DB_HOST"),
    port=os.getenv("ACEX_DB_PORT"),
    backend=os.getenv("ACEX_DB_BACKEND"),
)

# # External datasources
#netbox = Netbox(
#   url="https://netbox.example.net/",
#   token=os.getenv("NETBOX_TOKEN"),
#   verify_ssl=False,
#)

dev_mode = Settings(dev=True)

ae = AutomationEngine(
    db_connection=db,
    # assets_plugin=netbox,
    # logical_nodes_plugin=netbox,
    settings=dev_mode, # Run in dev mode, comment if you want to run in prod
)

# OIDC authentication
if not dev_mode.dev:
    ae.set_oidc(
        issuer_url=os.getenv("ACEX_OIDC_ISSUER_URL", "https://keycloak.example.net/realms/acex"),
        audience=os.getenv("ACEX_OIDC_AUDIENCE", "acex"),
        verify_ssl=False,
    )

# InfluxDB integration (optional)
#ae.set_influxdb(
#    url=os.getenv("ACEX_INFLUXDB_URL"),
#    token=os.getenv("ACEX_INFLUXDB_TOKEN"),
#    database="acex",
#    content_encoding="gzip",
#    version="v3"
#)

# AI OPS
#ae.ai_ops(
#    enabled=True,
#    providers=[
#        {
#            "name": "bergetai",
#            "base_url": os.getenv("ACEX_AI_API_BASEURL"),
#            "api_key": os.getenv("ACEX_AI_API_KEY"),
#        },
#    ],
#    chains={
#        "default": ["bergetai/moonshotai/Kimi-K3"],
#    },
#    mcp_server_url=os.getenv("ACEX_MCP_URL"),
#)

# ae.add_integration("ipam", netbox)
ae.add_configmap_dir("config_maps")

# CORS
ae.add_cors_allowed_origin("*")

ae.set_encryption_key(os.getenv("ACEX_CREDENTIALS_ENCRYPTION_KEY"))

# Create the api app!
app = ae.create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
    )