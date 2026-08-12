"""Inventory namespace — covers everything under /inventory/* on the backend."""

from __future__ import annotations

from acex_client.http import RestClient
from acex_client.resources.inventory.asset_clusters import AssetClusters
from acex_client.resources.inventory.assets import Assets
from acex_client.resources.inventory.collection_agents import CollectionAgents
from acex_client.resources.inventory.contact_assignments import ContactAssignments
from acex_client.resources.inventory.contacts import Contacts
from acex_client.resources.inventory.credentials import (
    Credentials,
    NodeCredentials,
    SiteCredentials,
)
from acex_client.resources.inventory.logical_nodes import LogicalNodes
from acex_client.resources.inventory.management_connections import ManagementConnections
from acex_client.resources.inventory.node_instances import NodeInstances
from acex_client.resources.inventory.region_assignments import RegionAssignments
from acex_client.resources.inventory.regions import Regions
from acex_client.resources.inventory.sites import Sites


class InventoryNamespace:
    def __init__(self, rest: RestClient):
        self.sites = Sites(rest)
        self.regions = Regions(rest)
        self.region_assignments = RegionAssignments(rest)
        self.contacts = Contacts(rest)
        self.contact_assignments = ContactAssignments(rest)
        self.assets = Assets(rest)
        self.asset_clusters = AssetClusters(rest)
        self.collection_agents = CollectionAgents(rest)
        self.credentials = Credentials(rest)
        self.logical_nodes = LogicalNodes(rest)
        self.management_connections = ManagementConnections(rest)
        self.node_instances = NodeInstances(rest)
        self._rest = rest

    def node_credentials(self, node_id: int) -> NodeCredentials:
        """Credentials assigned to a specific node."""
        return NodeCredentials(self._rest, parent_id=node_id)

    def site_credentials(self, site_name: str) -> SiteCredentials:
        """Credentials assigned to a specific site."""
        return SiteCredentials(self._rest, parent_id=site_name)
