"""ACE-X API service entry point.

The app itself is assembled in app.py; configuration lives in config.py.
"""

from .app import create_app, create_engine, main, run

__all__ = ["create_app", "create_engine", "main", "run"]


if __name__ == "__main__":
    main()
