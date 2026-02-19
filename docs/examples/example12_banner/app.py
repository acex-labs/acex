from acex import AutomationEngine

from acex.plugins.integrations import Sqlite, Netbox
from acex.database import Connection
import os


# Database (Postgres)
db = Connection(
    dbname="mydb17",
    user="admin",
    password="admin123",
    host="localhost",
    backend="postgresql"
)

#db = Connection(
#    dbname="automation_framework",
#    user="acex_api",
#    password="",
#    host="10.116.132.85",
#    backend="postgresql"
#)

# # External datasources
netbox = Netbox(
    url="https://netbox.ngninfra.net/",
    token=os.getenv("NETBOX_TOKEN"),
    verify_ssl=False,
)

ae = AutomationEngine(
    db_connection=db
)

ae.add_integration("ipam", netbox)
ae.add_configmap_dir("config_maps")

# CORS
ae.add_cors_allowed_origin("*")

# Create the api app!
app = ae.create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=80,
    )
