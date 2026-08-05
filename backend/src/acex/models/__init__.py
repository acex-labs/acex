from acex.observability.agents.models import (
    OutputDestination,
    TelemetryAgent,
    TelemetryAgentCapabilityLink,
    TelemetryAgentMatchRule,
    TelemetryAgentNodeLink,
)
from acex_devkit.models import AttributeValue, ExternalValue

from .asset import Asset, AssetCluster, AssetClusterLink, AssetResponse, Ned
from .collection_agent import CollectionAgent, CollectionAgentMatchRule, CollectionAgentNodeLink
from .contacts import Contact, ContactAssignment, ContactResponse
from .credential import Credential, CredentialField, NodeCredential, SiteCredential
from .device_config import DeviceConfig, DeviceConfigResponse, StoredDeviceConfig
from .lldp_neighbor import LldpNeighbor
from .logical_node import LogicalNode, LogicalNodeConfigResponse, LogicalNodeListResponse, LogicalNodeResponse
from .management_connections import ManagementConnection, ManagementConnectionBase, ManagementConnectionResponse
from .node import Node, NodeListResponse, NodeResponse, NodeStatus
from .pagination import PaginatedResponse
from .regions import Region, RegionResponse, SiteRegionAssignment
from .sites import Site, SiteResponse

system_models = [
    Asset,
    Ned,
    LogicalNode,
    Node,
    Site,
    Contact,
    ContactAssignment,
    Region,
    SiteRegionAssignment,
    TelemetryAgent,
    TelemetryAgentNodeLink,
    TelemetryAgentCapabilityLink,
    TelemetryAgentMatchRule,
    OutputDestination,
    CollectionAgent,
    CollectionAgentNodeLink,
    CollectionAgentMatchRule,
    LldpNeighbor,
    Credential,
    CredentialField,
    NodeCredential,
    SiteCredential,
]

__all__ = [
    "OutputDestination",
    "TelemetryAgent",
    "TelemetryAgentCapabilityLink",
    "TelemetryAgentMatchRule",
    "TelemetryAgentNodeLink",
    "AttributeValue",
    "ExternalValue",
    "Asset",
    "AssetCluster",
    "AssetClusterLink",
    "AssetResponse",
    "Ned",
    "CollectionAgent",
    "CollectionAgentMatchRule",
    "CollectionAgentNodeLink",
    "Contact",
    "ContactAssignment",
    "ContactResponse",
    "Credential",
    "CredentialField",
    "NodeCredential",
    "SiteCredential",
    "DeviceConfig",
    "DeviceConfigResponse",
    "StoredDeviceConfig",
    "LldpNeighbor",
    "LogicalNode",
    "LogicalNodeConfigResponse",
    "LogicalNodeListResponse",
    "LogicalNodeResponse",
    "ManagementConnection",
    "ManagementConnectionBase",
    "ManagementConnectionResponse",
    "Node",
    "NodeListResponse",
    "NodeResponse",
    "NodeStatus",
    "PaginatedResponse",
    "Region",
    "RegionResponse",
    "SiteRegionAssignment",
    "Site",
    "SiteResponse",
    "system_models",
]
