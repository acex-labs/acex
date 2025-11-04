from acex import AutomationEngine

from acex.plugins.integrations import Sqlite, Netbox
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
netbox = Netbox(
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

# Create the api app!
app = ae.create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=80,
    )
    