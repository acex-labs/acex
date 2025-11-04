from acex.plugins.adaptors import AssetAdapter, LogicalNodeAdapter, NodeAdapter
from acex.plugins.integrations import IntegrationPluginBase, DatabasePlugin
from acex.models import Asset, LogicalNode, Node
from acex.inventory.logical_node_service import LogicalNodeService
from acex.inventory.node_service import NodeService


class Inventory: 

    def __init__(
            self, 
            db_connection = None,
            assets_plugin = None,
            logical_nodes_plugin = None,
            config_compiler = None,
            integrations = None,
        ):

        # För presistent storage monteras en postgresql anslutning
        # Används inte specifika plugins för assets eller logical nodes
        # så används tabeller i databasen.

        # monterar datasources som datastores med specifika adaptrar
        print(f"asset plugin: {assets_plugin}")
        if assets_plugin:
            self.assets = AssetAdapter(assets_plugin)
        else:
            print("No assets plugin, using database")
            default_assets_plugin = DatabasePlugin(db_connection, Asset)
            self.assets = AssetAdapter(default_assets_plugin)

        # Logical Nodes - skapa adapter och wrappa i service layer
        if logical_nodes_plugin:
            print(f"logical nodes plugin: {logical_nodes_plugin}")
            logical_nodes_adapter = LogicalNodeAdapter(logical_nodes_plugin)
        else:
            print("No logical nodes plugin, using database")
            default_logical_nodes_plugin = DatabasePlugin(db_connection, LogicalNode)
            logical_nodes_adapter = LogicalNodeAdapter(default_logical_nodes_plugin)
        
        self.logical_nodes = LogicalNodeService(logical_nodes_adapter, config_compiler, integrations)

        # Node instances
        node_instance_plugin = DatabasePlugin(db_connection, Node)
        node_instances_adapter = NodeAdapter(node_instance_plugin)
        self.node_instances = NodeService(node_instances_adapter, self)

