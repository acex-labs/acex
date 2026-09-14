from acex import AutomationEngine

from acex.plugins.integrations import Sqlite, Netbox
from acex.database import Connection
import os

# Database (Postgres)
db = Connection(
    dbname="automation_framework",
    user="acex_api",
    password="",
    host="10.116.132.85",
    backend="postgresql"
)


# # External datasources
#netbox = Netbox(
#    url="https://netbox.ngninfra.net/",
#    token=os.getenv("NETBOX_TOKEN"),
#    verify_ssl=False,
#)

ae = AutomationEngine(
    db_connection=db,
    # assets_plugin=netbox,
    # logical_nodes_plugin=netbox,
)

#ae.add_integration("ipam", netbox)
ae.add_configmap_dir("config_maps")

# AI OPS
#ae.ai_ops(
#    enabled=True,
#    base_url=os.getenv("ACEX_AI_API_BASEURL"),
#    api_key=os.getenv("ACEX_AI_API_KEY"),
#    mcp_server_url=os.getenv("ACEX_MCP_URL")
#)

# CORS
#ae.add_cors_allowed_origin("*")

# Create the api app!
app = ae.create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )
    