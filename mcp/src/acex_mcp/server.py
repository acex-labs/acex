"""ACE-X MCP Server main entry point."""

from fastmcp import FastMCP
import requests

mcp = FastMCP("Acex-MCP")

# Backend API URL
BACKEND_API_URL = "http://localhost/api/v1"

@mcp.tool
def hello(name: str) -> str:
    return f"Hello, {name}!"

@mcp.tool
def get_assets() -> list:
    """
    Hämta alla assets från backend API.
    Asset = Switch/Firewall/Router

    En asset representerar en fysisk enhet (switch, router eller brandvägg) 
    och de attribut som hör till. 

    Returnerar en lista med enheter, varje enhet har attribut:
    - vendor
    - serialnumber
    - model
    - operativsystem
    """
    response = requests.get(f"{BACKEND_API_URL}/inventory/assets/")
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    mcp.run(transport="http", port=8000)