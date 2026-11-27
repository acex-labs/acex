"""The topology of a part of the network, as the LLDP/CDP layer sees it."""

import pytest
from acex.database import Connection, DatabaseManager
from acex.lldp.lldp_neighbor_manager import LldpNeighborManager
from acex.models import LogicalNode, Node
from acex.models.regions import SiteRegionAssignment
from acex.topology import LldpTopologySource, TopologyService
from acex_devkit.models.lldp_neighbor import LldpNeighborEntry, LldpNeighborUpload
from fastapi import HTTPException
from sqlmodel import Session


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(Connection(backend="sqlite", dbname="topology.db"))
    manager.create_tables()
    with Session(manager.connection.engine) as session:
        session.add(SiteRegionAssignment(region_name="north", site_name="sto"))
        session.add(SiteRegionAssignment(region_name="north", site_name="upp"))
        session.add(SiteRegionAssignment(region_name="nordics", site_name="sto"))
        session.add(SiteRegionAssignment(region_name="south", site_name="mmo"))
        session.commit()
    return manager


@pytest.fixture
def lldp(db):
    return LldpNeighborManager(db)


@pytest.fixture
def topology(db):
    return TopologyService(db, [LldpTopologySource()])


def add_node(db, hostname, site, role="access") -> int:
    with Session(db.connection.engine) as session:
        logical_node = LogicalNode(hostname=hostname, role=role, site=site)
        session.add(logical_node)
        session.commit()
        node = Node(asset_ref_id=logical_node.id, logical_node_id=logical_node.id)
        session.add(node)
        session.commit()
        return node.id


def report(lldp, node_id, *neighbors):
    """Each neighbor is (local interface, remote device, remote interface)."""
    entries = [LldpNeighborEntry(local_interface=a, remote_device=b, remote_interface=c) for a, b, c in neighbors]
    lldp.upload_neighbors(LldpNeighborUpload(node_instance_id=node_id, neighbors=entries))


def labels(graph) -> set[str]:
    return {node.label for node in graph.nodes}


def pairs(graph) -> set[frozenset[str]]:
    by_id = {node.id: node.label for node in graph.nodes}
    return {frozenset({by_id[link.a.node], by_id[link.b.node]}) for link in graph.links}


@pytest.fixture
def network(db, lldp):
    """sto-core links to sto-acc and upp-core; mmo-core links to upp-core; sto-acc sees an unmanaged AP."""
    sto_core = add_node(db, "sto-core", "sto", role="core")
    sto_acc = add_node(db, "sto-acc", "sto")
    upp_core = add_node(db, "upp-core", "upp", role="core")
    mmo_core = add_node(db, "mmo-core", "mmo", role="core")
    report(lldp, sto_core, ("Gi1", "sto-acc", "Gi49"), ("Gi2", "upp-core", "Gi2"))
    report(lldp, sto_acc, ("Gi49", "sto-core", "Gi1"), ("Gi1", "ap-1", "eth0"))
    report(lldp, upp_core, ("Gi2", "sto-core", "Gi2"))
    report(lldp, mmo_core, ("Gi3", "upp-core", "Gi3"))


class TestTheWholeNetwork:
    def should_have_every_link_once_though_both_ends_report_it(self, topology, network):
        graph = topology.graph()

        assert pairs(graph) == {
            frozenset({"sto-core", "sto-acc"}),
            frozenset({"sto-core", "upp-core"}),
            frozenset({"mmo-core", "upp-core"}),
            frozenset({"sto-acc", "ap-1"}),
        }
        assert len(graph.links) == 4

    def should_describe_each_node_with_its_site_regions_and_role(self, topology, network):
        nodes = {node.label: node for node in topology.graph().nodes}

        assert (nodes["sto-core"].site, nodes["sto-core"].regions, nodes["sto-core"].role) == (
            "sto",
            ["nordics", "north"],
            "core",
        )
        assert nodes["ap-1"].kind == "unmanaged"
        assert nodes["ap-1"].node_instance_id is None

    def should_have_every_node_in_scope(self, topology, network):
        assert all(node.in_scope for node in topology.graph().nodes)

    def should_name_the_layer_of_each_link(self, topology, network):
        graph = topology.graph()

        assert graph.layers == ["lldp"]
        assert {link.layer for link in graph.links} == {"lldp"}


class TestASite:
    def should_have_the_links_of_its_nodes_and_their_neighbours_out_of_scope(self, topology, network):
        graph = topology.graph(site="sto")

        assert labels(graph) == {"sto-core", "sto-acc", "upp-core", "ap-1"}
        assert {node.label for node in graph.nodes if not node.in_scope} == {"upp-core"}

    def should_have_a_node_of_it_that_has_no_links(self, topology, network, db):
        add_node(db, "sto-lonely", "sto")

        assert "sto-lonely" in labels(topology.graph(site="sto"))
        assert "sto-lonely" not in labels(topology.graph(site="upp"))

    def should_have_a_link_that_only_the_neighbour_out_of_scope_reports(self, topology, network, db, lldp):
        quiet = add_node(db, "upp-acc", "upp")
        report(lldp, add_node(db, "mmo-acc", "mmo"), ("Gi9", "upp-acc", "Gi9"))

        graph = topology.graph(site="upp")

        assert frozenset({"mmo-acc", "upp-acc"}) in pairs(graph)
        assert quiet in {node.node_instance_id for node in graph.nodes}


class TestARegion:
    def should_have_the_links_of_the_nodes_on_its_sites(self, topology, network):
        graph = topology.graph(region=["north"])

        assert {node.label for node in graph.nodes if node.in_scope} >= {"sto-core", "sto-acc", "upp-core"}
        assert {node.label for node in graph.nodes if not node.in_scope} == {"mmo-core"}

    def should_be_narrowed_by_a_site(self, topology, network):
        graph = topology.graph(region=["north"], site="upp")

        assert {node.label for node in graph.nodes if node.in_scope} == {"upp-core"}

    def should_be_empty_for_a_site_outside_it(self, topology, network):
        graph = topology.graph(region=["south"], site="sto")

        assert graph.nodes == [] and graph.links == []

    def should_take_the_whole_name(self, topology, network):
        assert topology.graph(region=["nor"]).links == []


class TestSeveralRegions:
    def should_have_the_sites_of_all_of_them(self, topology, network):
        graph = topology.graph(region=["north", "south"])

        devices = {node.label for node in graph.nodes if node.node_instance_id}
        assert devices == {"sto-core", "sto-acc", "upp-core", "mmo-core"}
        assert all(node.in_scope for node in graph.nodes)

    def should_be_narrowed_by_a_site_in_one_of_them(self, topology, network):
        graph = topology.graph(region=["north", "south"], site="mmo")

        assert {node.label for node in graph.nodes if node.in_scope} == {"mmo-core"}


class TestLayers:
    def should_list_the_layers_there_are(self, topology):
        assert [layer.key for layer in topology.layers()] == ["lldp"]

    def should_refuse_a_layer_that_does_not_exist(self, topology, network):
        with pytest.raises(HTTPException) as refused:
            topology.graph(layers=["lldp", "physical"])

        assert refused.value.status_code == 422
