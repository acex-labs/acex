"""Test-wide setup.

`ACEX_MCP_TRANSPORT` has to be set before acex_mcp is imported: config.Settings
is read once at import and bound into the other modules. stdio mode skips the
inbound-auth bootstrap, which would otherwise need a live backend just to build
the app and inspect its tools.
"""

import os

os.environ.setdefault("ACEX_MCP_TRANSPORT", "stdio")
