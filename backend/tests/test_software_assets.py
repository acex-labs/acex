"""Software compliance asset by asset: the assets of every node against the software policy, to filter and search."""

import asyncio
import random
from types import SimpleNamespace

import pytest
from acex.api.routers.compliance import create_router
from acex.compliance import ComplianceService, SoftwareAssets
from acex.compliance.software import ApprovedVersions, SoftwareCheck
from acex.database import Connection, DatabaseManager
from acex.inventory.asset_cluster_manager import AssetClusterManager
from acex.inventory.asset_service import AssetService
from acex.inventory.logical_node_service import LogicalNodeService
from acex.inventory.node_service import NodeService
from acex.models import Asset, AssetCluster, AssetClusterLink, Node
from acex.models.logical_node import LogicalNode
from acex.plugins.adaptors.asset_adapter import AssetAdapter
from acex.plugins.adaptors.logical_node_adapter import LogicalNodeAdapter
from acex.plugins.adaptors.node_adapter import NodeAdapter
from acex.plugins.integrations.database import DatabasePlugin
from acex_devkit.models.compliance import SoftwareStatus
from acex_devkit.models.node_response import AssetRefType
from acex_devkit.models.policy import SoftwarePolicyResponse
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session

URL = "/api/v1/compliance/software/assets"

APPROVED = [
    ("C9300-24T", "17.9.4a", True),
    ("C9300-24T", "17.6.5", False),
    (None, "17.12.3a", True),
]
REGIONS = {"sto": ["nordics"], "got": ["nordics"], "lab": ["nordics-lab", "labs"]}


class FakePolicies:
    def list_policies(self):
        return [
            policy(i, "cisco", model, "cisco_iosxe", version, golden)
            for i, (model, version, golden) in enumerate(APPROVED)
        ]


def policy(id, vendor, hardware_model, os, os_version, golden=False):
    return SoftwarePolicyResponse(
        id=id, vendor=vendor, hardware_model=hardware_model, os=os, os_version=os_version, golden=golden
    )


class FakeRegions:
    def list_assignments(self, site_names=None):
        return [
            SimpleNamespace(site_name=s, region_name=r)
            for s, regions in REGIONS.items()
            if site_names is None or s in site_names
            for r in regions
        ]


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = DatabaseManager(Connection(backend="sqlite", dbname="software_assets.db"))
    manager.create_tables()
    # What the database is asked, so a test can count the queries a request makes.
    manager.statements = []
    event.listen(manager.connection.engine, "before_cursor_execute", lambda *args: manager.statements.append(args[2]))
    return manager


def add_asset(db, serial, vendor, model, os, version):
    with Session(db.connection.engine) as session:
        asset = Asset(vendor=vendor, serial_number=serial, hardware_model=model, os=os, os_version=version)
        session.add(asset)
        session.commit()
        return asset.id


def add_node(db, ref_id, hostname, site, ref_type=AssetRefType.asset):
    with Session(db.connection.engine) as session:
        logical_node = LogicalNode(hostname=hostname, role="access", site=site, sequence=1)
        session.add(logical_node)
        session.flush()
        node = Node(asset_ref_id=ref_id, asset_ref_type=ref_type, logical_node_id=logical_node.id)
        session.add(node)
        session.commit()
        return node.id


def add_cluster(db, name, asset_ids):
    with Session(db.connection.engine) as session:
        cluster = AssetCluster(name=name)
        session.add(cluster)
        session.flush()
        for order, asset_id in enumerate(asset_ids):
            session.add(AssetClusterLink(asset_id=asset_id, cluster_id=cluster.id, order=order))
        session.commit()
        return cluster.id


@pytest.fixture
def inventory(db):
    """Seven assets on six nodes, one of the nodes a cluster of two; a loose asset and a node whose asset is gone."""
    ids = SimpleNamespace(
        golden=add_asset(db, "SN-GOLDEN", "cisco", "C9300-24T", "cisco_iosxe", "17.9.4a"),
        old=add_asset(db, "SN-OLD", "cisco", "C9300-24T", "cisco_iosxe", "17.3.1"),
        silent=add_asset(db, "SN-SILENT", "cisco", "C9300-48P", "cisco_iosxe", None),
        juniper=add_asset(db, "SN-JUNIPER", "juniper", "EX2300-24T", "juniper_junos", "22.4R1"),
        member_accepted=add_asset(db, "SN-STACK-1", "cisco", "C9300-24T", "cisco_iosxe", "17.6.5"),
        member_old=add_asset(db, "SN-STACK-2", "cisco", "c9300-24t", "cisco_iosxe", "17.3.1"),
        newest=add_asset(db, "SN-NEWEST", "cisco", "C9300-48P", "cisco_iosxe", "17.12.3a"),
        loose=add_asset(db, "SN-LOOSE", "cisco", "C9300-24T", "cisco_iosxe", "17.9.4a"),
    )
    cluster = add_cluster(db, "stack1", [ids.member_accepted, ids.member_old])
    ids.nodes = SimpleNamespace(
        golden=add_node(db, ids.golden, "sto-sw1", "sto"),
        old=add_node(db, ids.old, "sto-sw2", "sto"),
        silent=add_node(db, ids.silent, "got-sw3", "got"),
        juniper=add_node(db, ids.juniper, "lab-r1", "lab"),
        stack=add_node(db, cluster, "got-stack", "got", AssetRefType.asset_cluster),
        newest=add_node(db, ids.newest, "sto-sw6", "sto"),
        gone=add_node(db, 9999, "sto-ghost", "sto"),
    )
    return ids


@pytest.fixture
def service(db, inventory):
    return SoftwareAssets(db, SoftwareCheck(FakePolicies()), FakeRegions())


def serials(page):
    return [row.serial_number for row in page.items]


def test_every_asset_of_every_node_is_listed_once_a_clusters_members_each(service):
    page = service.query(sort="serial_number")

    assert serials(page) == [
        "SN-GOLDEN",
        "SN-JUNIPER",
        "SN-NEWEST",
        "SN-OLD",
        "SN-SILENT",
        "SN-STACK-1",
        "SN-STACK-2",
    ]
    assert page.total == 7


def test_an_asset_no_node_has_is_not_listed(service):
    assert "SN-LOOSE" not in serials(service.query())


def test_a_row_says_where_the_asset_is(service, inventory):
    rows = {row.serial_number: row for row in service.query().items}

    assert (rows["SN-GOLDEN"].hostname, rows["SN-GOLDEN"].site, rows["SN-GOLDEN"].regions) == (
        "sto-sw1",
        "sto",
        ["nordics"],
    )
    assert rows["SN-JUNIPER"].regions == ["labs", "nordics-lab"]
    assert rows["SN-GOLDEN"].node_id == inventory.nodes.golden
    assert rows["SN-GOLDEN"].cluster is None
    # A cluster's members are on its node, each with the cluster's name.
    assert {rows[s].node_id for s in ("SN-STACK-1", "SN-STACK-2")} == {inventory.nodes.stack}
    assert {rows[s].cluster for s in ("SN-STACK-1", "SN-STACK-2")} == {"stack1"}


def test_each_asset_has_its_status_and_the_version_to_aim_for(service):
    rows = {row.serial_number: (row.status, row.golden_version) for row in service.query().items}

    assert rows == {
        "SN-GOLDEN": (SoftwareStatus.golden, "17.9.4a"),
        "SN-OLD": (SoftwareStatus.not_allowed, "17.9.4a"),
        "SN-SILENT": (SoftwareStatus.unknown_version, "17.12.3a"),
        "SN-JUNIPER": (SoftwareStatus.no_policy, None),
        "SN-STACK-1": (SoftwareStatus.accepted, "17.9.4a"),
        "SN-STACK-2": (SoftwareStatus.not_allowed, "17.9.4a"),
        "SN-NEWEST": (SoftwareStatus.golden, "17.12.3a"),
    }


@pytest.fixture
def real_inventory(db):
    """The inventory services the compliance of the installation reads through, over the same database."""
    inventory = SimpleNamespace(
        assets=AssetService(AssetAdapter(DatabasePlugin(db, Asset)), hardware_models=SimpleNamespace()),
        logical_nodes=LogicalNodeService(
            LogicalNodeAdapter(DatabasePlugin(db, LogicalNode)),
            config_compiler=None,
            integrations=None,
            db_manager=db,
            telemetry_agent_manager=None,
        ),
        asset_cluster_manager=AssetClusterManager(db),
        credential_manager=None,
        region_assignment_manager=FakeRegions(),
    )
    inventory.node_instances = NodeService(NodeAdapter(DatabasePlugin(db, Node)), inventory)
    return inventory


def test_the_list_counts_the_assets_the_compliance_of_the_installation_counts(real_inventory, service):
    """The card is the sum of every node measured through the inventory services; the list reads the inventory in
    one go. They must count the same assets, or the number clicked is not the number landed on. The inventory has a
    cluster, a node whose asset is gone and an asset no node has: the cases where the two readings could part."""

    async def no_configuration(node_instance_id):
        return None

    compliance = ComplianceService(real_inventory, device_config_manager=None, software_policies=FakePolicies())
    compliance.configuration.differ = SimpleNamespace(observed=no_configuration)
    card = asyncio.run(compliance.overview()).summary.software
    page = service.query(limit=1000)

    assert page.total == card.assets_total == 7
    assert page.status_counts == {
        SoftwareStatus.golden: card.golden_count,
        SoftwareStatus.accepted: card.accepted_count,
        SoftwareStatus.not_allowed: card.not_allowed_count,
        SoftwareStatus.no_policy: card.no_policy_count,
        SoftwareStatus.unknown_version: card.unknown_version_count,
    }


def test_the_assets_not_on_an_approved_version_come_first_by_default(service):
    statuses = [row.status for row in service.query().items]

    assert statuses == [
        SoftwareStatus.not_allowed,
        SoftwareStatus.not_allowed,
        SoftwareStatus.unknown_version,
        SoftwareStatus.no_policy,
        SoftwareStatus.accepted,
        SoftwareStatus.golden,
        SoftwareStatus.golden,
    ]
    # Ties go by hostname.
    assert [row.hostname for row in service.query().items][:2] == ["got-stack", "sto-sw2"]


def test_the_list_can_be_narrowed_to_some_statuses(service):
    page = service.query(status=[SoftwareStatus.not_allowed, SoftwareStatus.unknown_version])

    assert sorted(serials(page)) == ["SN-OLD", "SN-SILENT", "SN-STACK-2"]
    assert page.total == 3


def test_the_counts_leave_out_the_status_filter_so_each_status_can_show_its_size(service):
    page = service.query(status=[SoftwareStatus.golden])

    assert page.total == 2
    assert page.status_counts == {
        SoftwareStatus.golden: 2,
        SoftwareStatus.accepted: 1,
        SoftwareStatus.not_allowed: 2,
        SoftwareStatus.no_policy: 1,
        SoftwareStatus.unknown_version: 1,
    }


def test_the_counts_follow_every_other_filter(service):
    page = service.query(site="sto", status=[SoftwareStatus.golden])

    assert page.status_counts[SoftwareStatus.not_allowed] == 1
    assert page.status_counts[SoftwareStatus.no_policy] == 0
    assert sum(page.status_counts.values()) == 3


@pytest.mark.parametrize(
    "filters, expected",
    [
        ({"site": "got"}, ["SN-SILENT", "SN-STACK-1", "SN-STACK-2"]),
        ({"site": "GOT"}, ["SN-SILENT", "SN-STACK-1", "SN-STACK-2"]),
        ({"region": "nordics"}, ["SN-GOLDEN", "SN-NEWEST", "SN-OLD", "SN-SILENT", "SN-STACK-1", "SN-STACK-2"]),
        ({"region": "labs"}, ["SN-JUNIPER"]),
        ({"region": "nord"}, []),  # a region by its whole name
        ({"site": "sto", "region": "nordics"}, ["SN-GOLDEN", "SN-NEWEST", "SN-OLD"]),
        ({"site": "lab", "region": "nordics"}, []),  # the site is in other regions, not this one
        ({"region": "nordics", "status": [SoftwareStatus.not_allowed]}, ["SN-OLD", "SN-STACK-2"]),
    ],
)
def test_the_filters_narrow_the_list_together(service, filters, expected):
    assert sorted(serials(service.query(**filters))) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("sn-old", ["SN-OLD"]),  # serial number
        ("sto-sw", ["SN-GOLDEN", "SN-NEWEST", "SN-OLD"]),  # hostname
        ("EX2300", ["SN-JUNIPER"]),  # hardware model
        ("junos", ["SN-JUNIPER"]),  # OS
        ("17.6", ["SN-STACK-1"]),  # running version
        ("stack1", ["SN-STACK-1", "SN-STACK-2"]),  # cluster
        ("  sn-old  ", ["SN-OLD"]),
        ("%", []),  # a typed % is that character
        ("nothing like this", []),
    ],
)
def test_one_search_text_looks_through_what_identifies_an_asset(service, text, expected):
    assert sorted(serials(service.query(q=text))) == expected


def test_the_search_narrows_together_with_the_filters(service):
    assert serials(service.query(q="sto-sw", status=[SoftwareStatus.not_allowed])) == ["SN-OLD"]


def test_versions_sort_by_number_not_by_text(service):
    page = service.query(sort="os_version")

    # Each OS on its own, one after the other. Within one, 17.12 follows 17.9, which a sort by text would not do, and
    # an asset that reported no version is last.
    assert [row.os_version for row in page.items] == [
        "17.3.1",
        "17.3.1",
        "17.6.5",
        "17.9.4a",
        "17.12.3a",
        None,
        "22.4R1",
    ]


def test_descending_reverses_the_order(service):
    up = serials(service.query(sort="serial_number"))

    assert serials(service.query(sort="serial_number", order="desc")) == up[::-1]


def test_an_unknown_sort_field_is_refused(service):
    with pytest.raises(HTTPException) as refused:
        service.query(sort="password")

    assert refused.value.status_code == 400
    assert "hostname" in refused.value.detail


def test_pages_follow_each_other_without_a_gap_or_a_repeat(service):
    everything = serials(service.query(limit=100))
    pages = [service.query(limit=3, offset=offset) for offset in (0, 3, 6)]

    assert [serials(p) for p in pages] == [everything[0:3], everything[3:6], everything[6:7]]
    assert {p.total for p in pages} == {7}
    assert service.query(limit=3, offset=30).items == []


def test_however_many_nodes_there_are_the_inventory_is_read_in_two_queries(db, service):
    for n in range(40):
        add_node(db, add_asset(db, f"SN-X{n}", "cisco", "C9300-24T", "cisco_iosxe", "17.9.4a"), f"x-{n}", "sto")
    db.statements.clear()

    page = service.query(limit=5)

    assert page.total == 47
    assert len(db.statements) == 2


def test_an_asset_found_by_the_policy_index_is_the_one_a_scan_of_the_policy_would_find():
    """The index only makes finding fast; it must find what going through the whole policy found."""
    rng = random.Random(7)
    vendors, systems = ["cisco", "juniper"], ["cisco_iosxe", "cisco_nxos", "juniper_junos"]
    models = ["C9300-24T", "c9300-24t", "C9300-48P", "N9K", None, None]
    approved = [
        policy(i, rng.choice(vendors), rng.choice(models), rng.choice(systems), f"17.{i % 9}.1", golden=i % 5 == 0)
        for i in range(120)
    ]
    index = ApprovedVersions(approved)

    for _ in range(500):
        asset = SimpleNamespace(
            vendor=rng.choice(vendors),
            os=rng.choice(systems),
            hardware_model=rng.choice([m for m in models if m] + ["C9300-24t"]),
            os_version=None,
        )
        on_os = [v for v in approved if v.vendor == asset.vendor and v.os == asset.os]
        for_model = [
            v for v in on_os if v.hardware_model and v.hardware_model.casefold() == asset.hardware_model.casefold()
        ]
        scanned = for_model or [v for v in on_os if v.hardware_model is None]

        assert [p.id for _, p in index.covering(asset)] == [v.id for v in scanned]


@pytest.fixture
def api(db, inventory):
    engine = SimpleNamespace(
        inventory=SimpleNamespace(region_assignment_manager=FakeRegions()),
        device_config_manager=None,
        software_policies=FakePolicies(),
        db=db,
    )
    app = FastAPI()
    app.include_router(create_router(engine))
    return TestClient(app)


def test_the_page_is_served_with_its_filters_from_the_query_string(api):
    body = api.get(URL, params={"status": ["not_allowed", "unknown_version"], "site": "got", "limit": 2}).json()

    assert body["total"] == 2
    assert {row["serial_number"] for row in body["items"]} == {"SN-SILENT", "SN-STACK-2"}
    assert body["limit"] == 2 and body["offset"] == 0
    assert body["status_counts"]["unknown_version"] == 1
    assert set(body["items"][0]) >= {"asset_id", "node_id", "hostname", "site", "regions", "status", "golden_version"}


def test_an_unknown_status_or_a_page_out_of_bounds_is_refused(api):
    assert api.get(URL, params={"status": "fine"}).status_code == 422
    assert api.get(URL, params={"limit": 0}).status_code == 422
    assert api.get(URL, params={"limit": 5000}).status_code == 422
    assert api.get(URL, params={"offset": -1}).status_code == 422
    assert api.get(URL, params={"sort": "password"}).status_code == 400
