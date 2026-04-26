
from .asset import Asset, AssetCluster, AssetClusterLink, AssetResponse, Ned
from .logical_node import LogicalNode, LogicalNodeResponse, LogicalNodeListResponse
from .node import Node, NodeResponse, NodeListResponse, NodeStatus
#from .external_value import ExternalValue
#from .attribute_value import AttributeValue
from acex_devkit.models import ExternalValue, AttributeValue
from .device_config import StoredDeviceConfig, DeviceConfig, DeviceConfigResponse
from .management_connections import ManagementConnection, ManagementConnectionResponse, ManagementConnectionBase
from .sites import Site, SiteResponse
from .contacts import Contact, ContactResponse, ContactAssignment
from .telemetry_agent import TelemetryAgent, TelemetryAgentNodeLink, TelemetryAgentCapabilityLink, TelemetryAgentMatchRule, OutputDestination
from .collection_agent import CollectionAgent, CollectionAgentNodeLink, CollectionAgentMatchRule
from .pagination import PaginatedResponse

system_models = [Asset, Ned, LogicalNode, Node, Site, Contact, ContactAssignment, TelemetryAgent, TelemetryAgentNodeLink, TelemetryAgentCapabilityLink, TelemetryAgentMatchRule, OutputDestination, CollectionAgent, CollectionAgentNodeLink, CollectionAgentMatchRule]