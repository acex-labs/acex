"""Entry point for `python -m acex_mcp`.

Delegates to the same run() the `acex-mcp` console script uses, so both ways
of starting the server behave identically.
"""

from acex_mcp.server import run

if __name__ == "__main__":
    run()
