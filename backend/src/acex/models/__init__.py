
from .asset import Asset, AssetInterface, AssetResponse, Ned
from .logical_node import LogicalNode, LogicalNodeResponse, LogicalNodeListResponse
from .node import Node, NodeResponse
from .external_value import ExternalValue
from .single_attribute import SingleAttribute
from .device_config import StoredDeviceConfig, DeviceConfig
from .management_connections import ManagementConnection, ManagementConnectionResponse, ManagementConnectionBase

system_models = [Asset, Ned, LogicalNode, Node]