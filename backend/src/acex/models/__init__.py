
from .asset import Asset, AssetCluster, AssetClusterLink, AssetResponse, Ned
from .logical_node import LogicalNode, LogicalNodeResponse, LogicalNodeListResponse
from .node import Node, NodeResponse
#from .external_value import ExternalValue
#from .attribute_value import AttributeValue
from acex_devkit.models import ExternalValue, AttributeValue
from .device_config import StoredDeviceConfig, DeviceConfig, DeviceConfigResponse
from .management_connections import ManagementConnection, ManagementConnectionResponse, ManagementConnectionBase

system_models = [Asset, Ned, LogicalNode, Node]