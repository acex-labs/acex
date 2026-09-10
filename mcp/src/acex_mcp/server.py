"""ACE-X MCP server entry point.

The server itself is assembled in app.py; the tools live under tools/.
"""

from .app import create_app, run

__all__ = ["create_app", "run"]


if __name__ == "__main__":
    run()
