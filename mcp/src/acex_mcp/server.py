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
def list_assets() -> list:
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

@mcp.tool
def list_logical_nodes() -> list:
    """
    Hämta alla logiska noder från backend API.
    Logical_Node attributes:
    - site
    - id
    - role
    - sequence

    """
    response = requests.get(f"{BACKEND_API_URL}/inventory/logical_nodes/")
    response.raise_for_status()
    return response.json()

@mcp.tool
def get_specific_logical_node(logical_node_id: str) -> dict:
    """
    Hämta specifik logical_node från backend API.
    Logical_Node attributes:
    - site
    - id
    - role
    - sequence
    - Configuration

    Configuration attributet håller all konfiguration som appliceras på en nod på ett vendor-agnostiskt
    sätt. 

    Configuration attributes:
    - System:
        - contact
        - hostname
        - domain-name
        - location
    - acl
    - lldp
    - interfaces:
        - List[Interfaces]
    - network-instances.
    - metadata:
      - information om hur kompilering gått och vilka funktioner som körts.

    """
    response = requests.get(f"{BACKEND_API_URL}/inventory/logical_nodes/{logical_node_id}")
    response.raise_for_status()
    return response.json()


@mcp.tool
def list_node_instances() -> list:
    """
    Hämta alla node-instances backend API.

    NodeInstance:
     - asset_id
     - logical_node_id
    """
    response = requests.get(f"{BACKEND_API_URL}/inventory/node_instances/")
    response.raise_for_status()
    return response.json()

@mcp.tool
def get_node_instance(id: int) -> dict:
    """
    Hämta alla node-instances backend API.

    NodeInstance:
     - asset_id
     - logical_node_id

     När en specific instans efterfrågas kommer den kompileras med all konfiguration. 
    """
    response = requests.get(f"{BACKEND_API_URL}/inventory/node_instances/{id}")
    response.raise_for_status()
    return response.json()

@mcp.tool
def get_node_instance_config(id: int) -> dict:
    """
    Hämtar senaste running-config för en specifik node instans

    Responsen finns i content och är base64 decodad.
    """
    response = requests.get(f"{BACKEND_API_URL}/operations/device_configs/{id}/latest")
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)