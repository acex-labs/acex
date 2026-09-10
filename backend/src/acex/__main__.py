"""Entry point for `python -m acex`.

Boots the AutomationEngine ASGI app with uvicorn.
"""

import os

import uvicorn
from acex import AutomationEngine
from acex.database import Connection


def create_app():
    """Build the FastAPI app (shared by __main__ and tests)."""
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
    return ae.create_app()


def main():
    app = create_app()
    uvicorn.run(
        app,
        host=os.getenv("ACEX_HOST", "0.0.0.0"),
        port=int(os.getenv("ACEX_PORT", "8080")),
    )


if __name__ == "__main__":
    main()
