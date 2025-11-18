"""ACE-X MCP Server main entry point."""

from fastmcp import FastMCP
import requests
import os

mcp = FastMCP("Acex-MCP")

# Backend API URL
BACKEND_API_URL = os.getenv('ACEX_API_URL') or "http://localhost/api/v1"


@mcp.resource("acex://docs/system-architecture")
async def system_architecture():
    return """
ACE-X System Architecture Overview
===================================

ACE-X is a network automation system built around three core concepts:

1. ASSETS
---------
Physical hardware devices (switches, routers, firewalls)
- Represents the actual physical equipment
- Contains vendor-specific information (model, serial number, OS version)
- Independent of logical configuration
- Attributes:
  * vendor: Manufacturer (e.g., "Cisco", "Juniper")
  * model: Hardware model number
  * serial_number: Unique device identifier
  * operating_system: OS and version

2. LOGICAL NODES
----------------
Abstract network node definitions - the "what" and "how" of configuration
- Vendor-agnostic configuration template
- Defines desired state independent of physical hardware
- Can be assigned to any compatible asset
- Attributes:
  * site: Physical location
  * role: Function (e.g., "access-switch", "core-router")
  * sequence: Order/priority number
  * configuration: Complete vendor-agnostic config in json including:
    - system: hostname, contact, domain, location
    - interfaces: Physical and logical interfaces
    - network-instances: VLANs, VRFs, routing instances
    - acl: Access control lists
    - lldp: Link layer discovery settings

3. NODE INSTANCES
-----------------
The mapping between logical configuration and physical hardware
- Links a Logical Node to an Asset
- Represents a deployed configuration on actual hardware
- When queried, triggers compilation to vendor-specific format
- Attributes:
  * asset_id: Which physical device (links to Asset)
  * logical_node_id: Which configuration template (links to Logical Node)
  * compiled_config: Rendered vendor-specific configuration

KEY PRINCIPLE
-------------
Separation of concerns: Hardware (Assets) is separate from Configuration (Logical Nodes).
This allows reusing configurations across different hardware and easy hardware replacement.
"""

@mcp.resource("acex://docs/workflow-examples")
async def workflow_docs():
    return """
Common Workflows in ACE-X
=========================

VIEWING INVENTORY
-----------------
1. Use list_assets() to see all physical hardware
2. Use list_logical_nodes() to see all logical nodes as an overview, but does not contain any configurations.
3. Use get_specific_logical_node() to get more details about a logical node and its configuration in json.
4. Use get_specific_node_instance() to get more details about a logical node and its rendered configuration
5. Use get_node_instance_config() to get the last backup of the actual running-configuration of a device. Can be used for diff against desired config.

TROUBLESHOOTING
---------------
- Check metadata in logical node response for compilation errors
- Verify asset_id and logical_node_id exist before creating node instance
- Review configuration structure matches expected vendor-agnostic format
"""

@mcp.tool
def list_assets() -> list:
    """
    List all physical hardware devices (assets) in the system.
    
    Returns a list of assets where each asset represents physical hardware (switch, router, firewall).
    
    Each asset has these attributes:
    - id: Unique identifier
    - vendor: Manufacturer (e.g., "Cisco", "Juniper")
    - model: Hardware model
    - serial_number: Device serial number
    - operating_system: OS version
    
    Use this to see what physical hardware is available.
    """
    response = requests.get(f"{BACKEND_API_URL}/inventory/assets/")
    response.raise_for_status()
    return response.json()

@mcp.tool
def list_logical_nodes() -> list:
    """
    List all logical nodes (configuration templates) in the system.
    
    Returns a list of logical nodes. Each logical node represents a vendor-agnostic 
    configuration template that can be deployed to physical hardware.
    
    Each logical node has:
    - id: The logical_node_id (e.g., "R1", "SW-Core-01") - USE THIS as logical_node_id parameter
    - site: Location (e.g., "HQ", "cph01")
    - role: Function (e.g., "core", "access-switch")
    - sequence: Order number
    - hostname: Device hostname
    
    NOTE: To get the actual configuration, use get_specific_logical_node(logical_node_id=<id>)
    """
    response = requests.get(f"{BACKEND_API_URL}/inventory/logical_nodes/")
    response.raise_for_status()
    return response.json()

@mcp.tool
def get_specific_logical_node(logical_node_id: str) -> dict:
    """
    Get detailed configuration for a specific logical node.
    
    Args:
        logical_node_id: The ID of the logical node (e.g., "R1", "SW-Core-01")
                        This is the 'id' field from list_logical_nodes()
    
    Returns the complete DESIRED configuration for this logical node including:
    - site: Location
    - id: logical_node_id
    - role: Function (core, access, etc.)
    - sequence: Order number
    - hostname: Device hostname
    - configuration: Complete vendor-agnostic configuration with:
        - system: hostname, contact, domain-name, location
        - interfaces: List of interface configurations
        - network-instances: VLANs, VRFs, routing instances
        - acl: Access control lists
        - lldp: Link layer discovery settings
    - metadata: Compilation status and applied functions
    
    This shows what the configuration SHOULD BE (desired state).
    """
    response = requests.get(f"{BACKEND_API_URL}/inventory/logical_nodes/{logical_node_id}")
    response.raise_for_status()
    return response.json()


@mcp.tool
def list_node_instances() -> list:
    """
    List all node instances (deployed configurations).
    
    A node instance links a logical node (configuration) to a physical asset (hardware).
    
    Returns a list where each node instance has:
    - id: Unique instance ID (integer) - USE THIS for get_node_instance() and get_node_instance_config()
    - asset_id: Which physical device (links to assets)
    - logical_node_id: Which configuration template (links to logical nodes)
    - hostname: Inherited from logical node
    
    Use this to see which configurations are deployed on which hardware.
    """
    response = requests.get(f"{BACKEND_API_URL}/inventory/node_instances/")
    response.raise_for_status()
    return response.json()

@mcp.tool
def get_node_instance(id: int) -> dict:
    """
    Get a specific node instance with its COMPILED vendor-specific configuration.
    
    Args:
        id: The node instance ID (integer) from list_node_instances()
    
    Returns:
    - id: Instance ID
    - asset_id: Physical device ID
    - logical_node_id: Configuration template ID
    - compiled_config: The DESIRED config translated to vendor-specific CLI commands
    
    This shows the desired configuration in vendor-specific format (e.g., Cisco IOS commands).
    Use get_node_instance_config() to get the actual RUNNING config from the device.
    """
    response = requests.get(f"{BACKEND_API_URL}/inventory/node_instances/{id}")
    response.raise_for_status()
    return response.json()

@mcp.tool
def get_node_instance_config(id: int) -> dict:
    """
    Get the latest RUNNING configuration stored in backend for a node instance.
    
    Args:
        id: The node instance ID (integer) from list_node_instances()
    
    Returns the actual running config that was last retrieved from the device.
    This is stored in the backend database and represents the real deployed state.
    
    Response contains:
    - content: The running configuration (base64 decoded)
    - timestamp: When this config was retrieved
    - node_instance_id: Which instance this belongs to
    
    Use this to see what is ACTUALLY running on the device (current state).
    Compare with get_node_instance() to see desired vs. actual differences.
    """
    response = requests.get(f"{BACKEND_API_URL}/operations/device_configs/{id}/latest")
    response.raise_for_status()
    return response.json()

def run():
    """Entry point for CLI command 'acex-mcp'"""
    mcp.run(transport="http", host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run()