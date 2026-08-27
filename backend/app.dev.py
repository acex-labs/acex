import importlib.metadata as _im
import os


_orig_version = _im.version
def _version(name, **kw):
    try:
        return _orig_version(name, **kw)
    except _im.PackageNotFoundError:
        return os.getenv("ACEX_VERSION", "dev")
_im.version = _version

import uvicorn
from acex import AutomationEngine
from acex.database import Connection

db = Connection(
    backend="postgresql",
    dbname=os.getenv("DB_NAME", "ace"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", ""),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
)

ae = AutomationEngine(db_connection=db)
ae.add_cors_allowed_origin("*")

app = ae.create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
