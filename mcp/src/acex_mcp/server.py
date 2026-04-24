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
def list_assets(
    vendor: str = None,
    os: str = None,
    hardware_model: str = None,
    ned_id: str = None,
    serial_number: str = None,
    assigned: bool = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """
    List physical hardware devices (assets) in the system.

    Returns a paginated response with items, total count, limit, and offset.
    Each asset represents physical hardware (switch, router, firewall).

    Args:
        vendor: Filter by manufacturer (e.g., "Cisco", "Juniper")
        os: Filter by operating system
        hardware_model: Filter by hardware model
        ned_id: Filter by NED ID
        serial_number: Filter by serial number
        assigned: Filter by assignment status (true = assigned to a node instance)
        limit: Max number of results (default 100)
        offset: Pagination offset (default 0)

    Each asset has these attributes:
    - id: Unique identifier
    - vendor: Manufacturer
    - serial_number: Device serial number
    - os / os_version: Operating system info
    - hardware_model: Hardware model
    - ned_id: NED identifier

    Use this to see what physical hardware is available.
    """
    params = {"limit": limit, "offset": offset}
    if vendor is not None:
        params["vendor"] = vendor
    if os is not None:
        params["os"] = os
    if hardware_model is not None:
        params["hardware_model"] = hardware_model
    if ned_id is not None:
        params["ned_id"] = ned_id
    if serial_number is not None:
        params["serial_number"] = serial_number
    if assigned is not None:
        params["assigned"] = assigned
    response = requests.get(f"{BACKEND_API_URL}/inventory/assets/", params=params)
    response.raise_for_status()
    return response.json()

@mcp.tool
def list_logical_nodes(
    role: str = None,
    site: str = None,
    sequence: int = None,
    hostname: str = None,
    assigned: bool = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """
    List logical nodes (configuration templates) in the system.

    Returns a paginated response with items, total count, limit, and offset.
    Each logical node represents a vendor-agnostic configuration template
    that can be deployed to physical hardware.

    Args:
        role: Filter by role (e.g., "core", "access-switch")
        site: Filter by site/location (e.g., "HQ", "cph01")
        sequence: Filter by sequence number
        hostname: Filter by hostname
        assigned: Filter by assignment status (true = assigned to a node instance)
        limit: Max number of results (default 100)
        offset: Pagination offset (default 0)

    Each logical node has:
    - id: The logical_node_id - USE THIS as logical_node_id parameter
    - site: Location
    - role: Function
    - sequence: Order number
    - hostname: Device hostname

    NOTE: To get the actual configuration, use get_specific_logical_node(logical_node_id=<id>)
    """
    params = {"limit": limit, "offset": offset}
    if role is not None:
        params["role"] = role
    if site is not None:
        params["site"] = site
    if sequence is not None:
        params["sequence"] = sequence
    if hostname is not None:
        params["hostname"] = hostname
    if assigned is not None:
        params["assigned"] = assigned
    response = requests.get(f"{BACKEND_API_URL}/inventory/logical_nodes/", params=params)
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
def list_node_instances(
    site: str = None,
    hostname: str = None,
    logical_node_id: int = None,
    asset_ref_id: int = None,
    status: str = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """
    List node instances (deployed configurations).

    A node instance links a logical node (configuration) to a physical asset (hardware).

    Returns a paginated response with items, total count, limit, and offset.

    Args:
        site: Filter by site/location
        hostname: Filter by hostname
        logical_node_id: Filter by logical node ID
        asset_ref_id: Filter by asset reference ID
        status: Filter by status ("planned", "init", "active", "decommissioned")
        limit: Max number of results (default 100)
        offset: Pagination offset (default 0)

    Each node instance has:
    - id: Unique instance ID (integer) - USE THIS for get_node_instance() and get_node_instance_config()
    - asset_ref_id: Which physical device (links to assets)
    - logical_node_id: Which configuration template (links to logical nodes)
    - hostname: Inherited from logical node
    - site, vendor, os, ned_id: Denormalized fields
    - status: Current status
    - created_at / updated_at: Timestamps

    Use this to see which configurations are deployed on which hardware.
    """
    params = {"limit": limit, "offset": offset}
    if site is not None:
        params["site"] = site
    if hostname is not None:
        params["hostname"] = hostname
    if logical_node_id is not None:
        params["logical_node_id"] = logical_node_id
    if asset_ref_id is not None:
        params["asset_ref_id"] = asset_ref_id
    if status is not None:
        params["status"] = status
    response = requests.get(f"{BACKEND_API_URL}/inventory/node_instances/", params=params)
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