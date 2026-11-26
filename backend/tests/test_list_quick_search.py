"""``q`` on the inventory lists: one search text across the fields that name a row.

The real services run over SQLite, as in ``test_asset_search.py`` (assets) and ``test_regions.py`` (sites, regions).
"""

import asyncio
from types import SimpleNamespace

import pytest
from acex.database import Connection, DatabaseManager
from acex.inventory.contact_service import ContactService
from acex.inventory.logical_node_service import LogicalNodeService
from acex.inventory.node_service import NodeService
from acex.inventory.region_assignment_manager import RegionAssignmentManager
from acex.inventory.region_service import RegionService
from acex.inventory.site_service import SiteService
from acex.models import Asset, Contact, LogicalNode, ManagementConnection, Node, Region, Site
from acex.models.regions import RegionAssignmentCreate, RegionBase
from acex.plugins.adaptors import RegionAdapter, SiteAdapter
from acex.plugins.adaptors.contact_adapter import ContactAdapter
from acex.plugins.adaptors.logical_node_adapter import LogicalNodeAdapter
from acex.plugins.adaptors.node_adapter import NodeAdapter
from acex.plugins.integrations.database import DatabasePlugin
from acex.search.match import MAX_ID_DIGITS, id_match
from acex_devkit.models.node_response import AssetRefType
from sqlalchemy import select
from sqlmodel import Session


def run(coroutine):
    return asyncio.run(coroutine)


@pytest.fixture
def inventory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = DatabaseManager(Connection(backend="sqlite", dbname="inventory.db"))
    db.create_tables()
    inventory = SimpleNamespace(db=db)
    inventory.sites = SiteService(SiteAdapter(DatabasePlugin(db, Site)), inventory=inventory)
    inventory.regions = RegionService(RegionAdapter(DatabasePlugin(db, Region)), inventory=inventory)
    inventory.region_assignment_manager = RegionAssignmentManager(db, inventory)
    inventory.contacts = ContactService(ContactAdapter(DatabasePlugin(db, Contact)))
    inventory.logical_nodes = LogicalNodeService(
        LogicalNodeAdapter(DatabasePlugin(db, LogicalNode)), config_compiler=None, integrations=None, db_manager=db
    )

    def get_asset(asset_id):
        with Session(db.connection.engine) as session:
            return session.get(Asset, asset_id)

    inventory.assets = SimpleNamespace(adapter=SimpleNamespace(get=get_asset))
    inventory.nodes = NodeService(NodeAdapter(DatabasePlugin(db, Node)), inventory)
    return inventory


def add_rows(inventory, *rows):
    with Session(inventory.db.connection.engine) as session:
        session.add_all(rows)
        session.commit()


def names(result):
    """What a list shows to name each row, sorted so no test depends on the database's order."""
    return sorted(getattr(item, "hostname", None) or item.name for item in result.items)


# ── sites ──────────────────────────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sites(inventory):
    add_rows(
        inventory,
        Site(
            name="stockholm-hq",
            display_name="Head Office",
            city="Stockholm",
            country="Sweden",
            address="Drottninggatan 1",
        ),
        Site(
            name="oslo-dc", display_name="Oslo Datacenter", city="Oslo", country="Norway", address="Karl Johans gate 5"
        ),
        Site(name="paris", city="Paris", country="France"),
    )
    return inventory


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        pytest.param("stockholm-hq", ["stockholm-hq"], id="name"),
        pytest.param("datacenter", ["oslo-dc"], id="display name"),
        pytest.param("PARIS", ["paris"], id="city, in any case"),
        pytest.param("norway", ["oslo-dc"], id="country"),
        pytest.param("karl johan", ["oslo-dc"], id="address"),
        pytest.param("  head  ", ["stockholm-hq"], id="trimmed"),
        pytest.param("not-a-site", [], id="no match"),
    ],
)
def test_a_site_is_found_by_any_of_its_identifying_fields(sites, q, expected):
    assert names(run(sites.sites.query(q=q))) == expected


@pytest.mark.parametrize("q", [None, "", "   "])
def test_a_blank_q_does_not_filter_the_sites(sites, q):
    assert names(run(sites.sites.query(q=q))) == ["oslo-dc", "paris", "stockholm-hq"]


def test_q_on_sites_counts_every_match_not_just_the_page(sites):
    first = run(sites.sites.query(q="o", limit=1))

    # "o" is in stockholm-hq, oslo-dc and Norway; paris has none.
    assert first.total == 2
    assert len(first.items) == 1


def test_q_on_sites_narrows_together_with_a_region(sites):
    # A region swaps the name filter for the names of its sites; q must still apply on top of it.
    run(sites.regions.create(RegionBase(name="nordics")))
    run(sites.regions.create(RegionBase(name="eu")))
    for region, site in (("nordics", "stockholm-hq"), ("nordics", "oslo-dc"), ("eu", "paris")):
        run(
            sites.region_assignment_manager.create_assignment(
                RegionAssignmentCreate(region_name=region, site_name=site)
            )
        )

    assert names(run(sites.sites.query(q="oslo", region="nordics"))) == ["oslo-dc"]
    assert names(run(sites.sites.query(q="paris", region="nordics"))) == []
    assert names(run(sites.sites.query(q="paris", region="eu"))) == ["paris"]


def test_wildcard_characters_are_matched_literally_in_the_sites(inventory):
    add_rows(inventory, Site(name="a_1"), Site(name="ab1"), Site(name="50%off"))

    assert names(run(inventory.sites.query(q="a_1"))) == ["a_1"]  # "_" is not "any one character"
    assert names(run(inventory.sites.query(q="%"))) == ["50%off"]  # "%" is not "anything"


# ── regions ────────────────────────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def regions(inventory):
    add_rows(
        inventory,
        Region(name="eu-north", display_name="Northern Europe"),
        Region(name="apac", display_name="Asia Pacific"),
    )
    return inventory


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        pytest.param("eu-nor", ["eu-north"], id="name"),
        pytest.param("northern", ["eu-north"], id="display name"),
        pytest.param("PACIFIC", ["apac"], id="display name, in any case"),
        pytest.param("p", ["apac", "eu-north"], id="contains, in either field (apac name, Europe)"),
        pytest.param("antarctica", [], id="no match"),
    ],
)
def test_a_region_is_found_by_its_name_or_display_name(regions, q, expected):
    assert names(run(regions.regions.query(q=q))) == expected


def test_q_on_regions_works_with_the_sites_included(regions):
    result = run(regions.regions.query(q="apac", include_sites=True))

    assert names(result) == ["apac"]
    assert result.total == 1


# ── contacts ───────────────────────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def contacts(inventory):
    add_rows(
        inventory,
        Contact(
            name="jdoe",
            display_name="Jane Doe",
            first_name="Jane",
            family_name="Doe",
            email="jane.doe@example.com",
            phone="+46 70 123 45 67",
        ),
        Contact(name="asmith", display_name="Alex Smith", email="alex@corp.example", phone="+47 99 888 77 66"),
        Contact(name="ls", family_name="Svensson"),
    )
    return inventory


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        pytest.param("asmith", ["asmith"], id="name"),
        pytest.param("alex smith", ["asmith"], id="display name"),
        pytest.param("CORP.EXAMPLE", ["asmith"], id="email, in any case"),
        pytest.param("70 123", ["jdoe"], id="phone"),
        pytest.param("svensson", ["ls"], id="family name (no other field of that contact has it)"),
        pytest.param("example", ["asmith", "jdoe"], id="more than one match"),
        pytest.param("nobody", [], id="no match"),
    ],
)
def test_a_contact_is_found_by_any_of_its_identifying_fields(contacts, q, expected):
    assert names(run(contacts.contacts.query(q=q))) == expected


def test_q_on_contacts_narrows_together_with_the_other_filters(contacts):
    assert names(run(contacts.contacts.query(q="example", name="jdoe"))) == ["jdoe"]
    assert names(run(contacts.contacts.query(q="example", name="ls"))) == []


# ── logical nodes ──────────────────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def logical_nodes(inventory):
    add_rows(
        inventory,
        LogicalNode(hostname="core-a", role="core", site="stockholm", sequence=1),
        LogicalNode(hostname="access-a", role="access", site="oslo", sequence=1),
        LogicalNode(hostname="edge-a", role="edge", site="oslo", sequence=1),
    )
    return inventory


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        pytest.param("core-a", ["core-a"], id="hostname"),
        pytest.param("STOCKHOLM", ["core-a"], id="site, in any case"),
        pytest.param("oslo", ["access-a", "edge-a"], id="site shared by two"),
        pytest.param("edge", ["edge-a"], id="role"),
        pytest.param("a", ["access-a", "core-a", "edge-a"], id="contains, not prefix"),
        pytest.param("nothing", [], id="no match"),
    ],
)
def test_a_logical_node_is_found_by_hostname_site_or_role(logical_nodes, q, expected):
    assert names(run(logical_nodes.logical_nodes.query(q=q))) == expected


def test_q_on_logical_nodes_narrows_together_with_the_other_filters(logical_nodes):
    assert names(run(logical_nodes.logical_nodes.query(q="oslo", role="edge"))) == ["edge-a"]
    assert names(run(logical_nodes.logical_nodes.query(q="oslo", site="stockholm"))) == []


def test_a_number_finds_the_logical_node_with_that_id_and_only_that_one(inventory):
    # Hostnames without digits, so only the id can match; 11 rows so that "1" is a prefix of "11".
    add_rows(inventory, *(LogicalNode(hostname=f"ln-{c}", role="core", site="lab", sequence=1) for c in "abcdefghijk"))

    assert names(run(inventory.logical_nodes.query(q="1"))) == ["ln-a"]
    assert names(run(inventory.logical_nodes.query(q="11"))) == ["ln-k"]


def test_a_number_too_large_for_an_id_finds_nothing_and_is_not_an_error(logical_nodes):
    assert names(run(logical_nodes.logical_nodes.query(q="9" * 25))) == []


# ── nodes ──────────────────────────────────────────────────────────────────────────────────────────────────────


def add_node(inventory, hostname, site, role, serial, model, vendor, ips=()):
    with Session(inventory.db.connection.engine) as session:
        logical_node = LogicalNode(hostname=hostname, role=role, site=site, sequence=1)
        asset = Asset(vendor=vendor, hardware_model=model, serial_number=serial, os="cisco_iosxe", os_version="17.9")
        session.add_all([logical_node, asset])
        session.flush()
        node = Node(asset_ref_id=asset.id, logical_node_id=logical_node.id)
        session.add(node)
        session.flush()
        for target_ip in ips:
            session.add(ManagementConnection(node_id=node.id, target_ip=target_ip, primary=True))
        session.commit()
        return node.id


@pytest.fixture
def nodes(inventory):
    # No node has a 3 anywhere (serial, model, IP) except as an id, so "3" finds the third node by its id alone.
    inventory.core = add_node(inventory, "core-a", "stockholm", "core", "FOC111", "C9500", "cisco", ["10.1.1.1"])
    inventory.edge = add_node(inventory, "edge-b", "oslo", "edge", "JN222", "MX204", "juniper", ["192.168.5.9"])
    inventory.dist = add_node(inventory, "dist-c", "lund", "dist", "SNCCC", "ABC", "arista")
    return inventory


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        pytest.param("core-a", ["core-a"], id="hostname"),
        pytest.param("OSLO", ["edge-b"], id="site, in any case"),
        pytest.param("dist", ["dist-c"], id="role"),
        pytest.param("168.5", ["edge-b"], id="management IP, as a contains and not a prefix"),
        pytest.param("10.1.", ["core-a"], id="management IP, as a prefix"),
        pytest.param("jn222", ["edge-b"], id="serial number"),
        pytest.param("c9500", ["core-a"], id="hardware model"),
        pytest.param("juniper", ["edge-b"], id="vendor (an enum column)"),
        pytest.param("nothing", [], id="no match"),
    ],
)
def test_a_node_is_found_by_what_names_it(nodes, q, expected):
    assert names(run(nodes.nodes.query(q=q))) == expected


def test_a_number_finds_the_node_with_that_id(nodes):
    assert nodes.dist == 3
    assert names(run(nodes.nodes.query(q=str(nodes.dist)))) == ["dist-c"]


def test_a_node_is_found_once_when_several_fields_match(nodes):
    # "e" is in the hostname, site and role of edge-b and in more of core-a's fields; every node counts once.
    result = run(nodes.nodes.query(q="e"))

    assert result.total == len(result.items) == len(set(names(result)))


def test_q_on_nodes_narrows_together_with_the_other_filters(nodes):
    assert names(run(nodes.nodes.query(q="1", site="stockholm"))) == ["core-a"]
    assert names(run(nodes.nodes.query(q="1", site="oslo"))) == ["edge-b"]  # "1" is also in 192.168.5.9
    assert names(run(nodes.nodes.query(q="10.1.", site="oslo"))) == []


def test_q_on_nodes_counts_every_match_not_just_the_page(nodes):
    first = run(nodes.nodes.query(q="1", limit=1))

    # "1" is in core-a's IP and serial and in edge-b's IP; dist-c has none, and its id is 3.
    assert first.total == 2
    assert len(first.items) == 1


def test_a_node_on_a_cluster_is_not_found_by_the_serial_of_an_asset_with_the_same_number(nodes):
    # asset_ref_id counts clusters and assets separately, so id 2 can be a cluster as well as the asset JN222.
    condition = NodeService._quick_match("JN222")
    with Session(nodes.db.connection.engine) as session:
        edge = session.get(Node, nodes.edge)
        assert session.scalars(select(Node.id).where(condition)).all() == [edge.id]

        edge.asset_ref_type = AssetRefType.asset_cluster
        session.add(edge)
        session.commit()

        assert session.scalars(select(Node.id).where(condition)).all() == []


# ── the id, as a number ────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("text", ["1", "42", "9" * MAX_ID_DIGITS])
def test_a_text_of_digits_is_an_id(text):
    assert id_match(text, Node.id) is not None


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("9" * (MAX_ID_DIGITS + 1), id="more digits than an id column holds"),
        pytest.param("-1", id="negative"),
        pytest.param("1.5", id="decimal"),
        pytest.param("12a", id="digits and letters"),
        pytest.param("٣", id="a digit that is not an ASCII one"),
        pytest.param("", id="empty"),
    ],
)
def test_other_texts_are_not_an_id(text):
    assert id_match(text, Node.id) is None
