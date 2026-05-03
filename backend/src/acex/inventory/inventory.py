from acex.plugins.adaptors import AssetAdapter, LogicalNodeAdapter, NodeAdapter, SiteAdapter, ContactAdapter
from acex.plugins.integrations import IntegrationPluginBase, DatabasePlugin
from acex.models import Asset, LogicalNode, Node, Site, Contact
from acex.inventory.asset_service import AssetService
from acex.inventory.logical_node_service import LogicalNodeService
from acex.inventory.node_service import NodeService
from acex.inventory.site_service import SiteService
from acex.inventory.contact_service import ContactService
from acex.inventory.asset_cluster_manager import AssetClusterManager
from acex.inventory.contact_assignment_manager import ContactAssignmentManager
from acex.inventory.collection_agent_manager import CollectionAgentManager
from acex.observability import TelemetryRegistry
from acex.observability.agents import TelemetryAgentManager
from acex.observability.renderers import GrafanaRenderer

class Inventory:

    def __init__(
            self,
            db_connection = None,
            assets_plugin = None,
            logical_nodes_plugin = None,
            sites_plugin = None,
            contacts_plugin = None,
            config_compiler = None,
            integrations = None,
            influxdb_settings = None,
        ):
        self.influxdb_settings = influxdb_settings

        # För presistent storage monteras en postgresql anslutning
        # Används inte specifika plugins för assets eller logical nodes
        # så används tabeller i databasen.

        # monterar datasources som datastores med specifika adaptrar
        print(f"asset plugin: {assets_plugin}")
        if assets_plugin:
            assets_adapter = AssetAdapter(assets_plugin)
        else:
            print("No assets plugin, using database")
            default_assets_plugin = DatabasePlugin(db_connection, Asset)
            assets_adapter = AssetAdapter(default_assets_plugin)

        self.assets = AssetService(assets_adapter)

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
        self.asset_cluster_manager = AssetClusterManager(db_connection)
        self.collection_agent_manager = CollectionAgentManager(db_connection)

        # Observability — intent-driven telemetry pipeline (telegraf + grafana)
        # derived from registered TelemetryComponents. Built lazily per request,
        # not persisted, so it always reflects current ACEX state. The
        # TelemetryAgentManager uses it as input source for telegraf config.
        self.telemetry_registry = TelemetryRegistry(db_connection)
        self.telemetry_agent_manager = TelemetryAgentManager(
            db_connection, self.telemetry_registry, influxdb_settings,
        )
        self.grafana_renderer = GrafanaRenderer(self.telemetry_registry, influxdb_settings)

        # Contacts
        if contacts_plugin:
            contact_adapter = ContactAdapter(contacts_plugin)
        else:
            default_contacts_plugin = DatabasePlugin(db_connection, Contact)
            contact_adapter = ContactAdapter(default_contacts_plugin)
        self.contacts = ContactService(contact_adapter)

        # Contact assignments (alltid databasbackad - limmet mellan contacts och sites)
        self.contact_assignment_manager = ContactAssignmentManager(db_connection, self)

        # Sites
        if sites_plugin:
            site_adapter = SiteAdapter(sites_plugin)
        else:
            default_sites_plugin = DatabasePlugin(db_connection, Site)
            site_adapter = SiteAdapter(default_sites_plugin)
        self.sites = SiteService(site_adapter, inventory=self)
