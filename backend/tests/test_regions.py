"""A region is found by its whole name.

The `name` filter of the inventory is a pattern (`ilike '%name%'`), which suits a search box. A lookup of one region
or one site by name must not use it as is: `eu` is also part of `eu-north`, `hq` part of `hq-2`. And a `region` filter
on a list means the region itself when it is given a whole region name, and every region that has it in its name
otherwise. These tests run the real region, site, node and assignment services over SQLite, with names that overlap.
"""

import asyncio
from types import SimpleNamespace

import pytest
from acex.database import Connection, DatabaseManager
from acex.inventory.logical_node_service import LogicalNodeService
from acex.inventory.node_service import NodeService
from acex.inventory.region_assignment_manager import RegionAssignmentManager
from acex.inventory.region_service import RegionService
from acex.inventory.site_service import SiteService
from acex.models import Asset, LogicalNode, Node, Region, Site
from acex.models.regions import RegionAssignmentCreate, RegionBase
from acex.plugins.adaptors import RegionAdapter, SiteAdapter
from acex.plugins.adaptors.logical_node_adapter import LogicalNodeAdapter
from acex.plugins.adaptors.node_adapter import NodeAdapter
from acex.plugins.integrations.database import DatabasePlugin
from fastapi import HTTPException
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
    return inventory


def add_region(inventory, name):
    return run(inventory.regions.create(RegionBase(name=name)))


def add_site(inventory, name, **fields):
    return inventory.sites.adapter.create(Site(name=name, **fields))


def assign(inventory, region, site):
    return run(
        inventory.region_assignment_manager.create_assignment(
            RegionAssignmentCreate(region_name=region, site_name=site)
        )
    )


def sites_of(inventory, region):
    return [s.name for s in run(inventory.regions.get(region.id)).sites]


def test_a_region_lists_its_own_sites_only(inventory):
    eu = add_region(inventory, "eu")
    north = add_region(inventory, "eu-north")
    add_site(inventory, "stockholm")
    add_site(inventory, "paris")
    assign(inventory, "eu-north", "stockholm")
    assign(inventory, "eu", "paris")

    assert sites_of(inventory, eu) == ["paris"]
    assert sites_of(inventory, north) == ["stockholm"]


def test_a_listing_of_regions_with_sites_does_the_same(inventory):
    add_region(inventory, "eu")
    add_region(inventory, "eu-north")
    add_site(inventory, "stockholm")
    assign(inventory, "eu-north", "stockholm")

    listed = run(inventory.regions.query(include_sites=True)).items

    assert {r.name: [s.name for s in r.sites] for r in listed} == {"eu": [], "eu-north": ["stockholm"]}


def test_a_site_is_the_one_of_that_name_when_another_name_contains_it(inventory):
    eu = add_region(inventory, "eu")
    add_site(inventory, "hq-2", latitude=2.0)  # first, so a pattern lookup of "hq" finds it first
    add_site(inventory, "hq", latitude=1.0)
    assign(inventory, "eu", "hq")

    listed = run(inventory.regions.get(eu.id)).sites

    assert [(s.name, s.latitude) for s in listed] == [("hq", 1.0)]


def test_a_site_can_join_a_region_whose_name_is_part_of_the_name_of_one_it_is_in(inventory):
    add_region(inventory, "eu")
    add_region(inventory, "eu-north")
    add_site(inventory, "stockholm")
    assign(inventory, "eu-north", "stockholm")

    assigned = assign(inventory, "eu", "stockholm")

    assert (assigned.region_name, assigned.site_name) == ("eu", "stockholm")


def test_the_same_assignment_twice_is_refused(inventory):
    add_region(inventory, "eu")
    add_site(inventory, "paris")
    assign(inventory, "eu", "paris")

    with pytest.raises(HTTPException) as refused:
        assign(inventory, "eu", "paris")

    assert refused.value.status_code == 409


def test_a_region_that_does_not_exist_cannot_be_assigned_when_a_longer_name_does(inventory):
    add_region(inventory, "eu-north")
    add_site(inventory, "stockholm")

    with pytest.raises(HTTPException) as refused:
        assign(inventory, "eu", "stockholm")

    assert refused.value.status_code == 404
    assert inventory.region_assignment_manager.list_assignments() == []


def test_a_site_that_does_not_exist_cannot_be_assigned_when_a_longer_name_does(inventory):
    add_region(inventory, "eu")
    add_site(inventory, "hq-2")

    with pytest.raises(HTTPException) as refused:
        assign(inventory, "eu", "hq")

    assert refused.value.status_code == 404
    assert inventory.region_assignment_manager.list_assignments() == []


# The `region` filter of the lists.


def regions_with_sites(inventory, sites_by_region):
    """Regions and their sites, such as {"eu": ["a"]}; a site is made once however many regions it is in."""
    made = set()
    for region, sites in sites_by_region.items():
        add_region(inventory, region)
        for site in sites:
            if site not in made:
                add_site(inventory, site)
                made.add(site)
            assign(inventory, region, site)


def names_in(inventory, region):
    return inventory.region_assignment_manager.site_names_in(region)


def test_a_whole_region_name_means_that_region_only(inventory):
    regions_with_sites(inventory, {"eu": ["a"], "eu-north": ["b"]})

    assert names_in(inventory, "eu") == ["a"]
    assert names_in(inventory, "eu-north") == ["b"]


def test_a_part_of_a_name_still_means_every_region_that_has_it(inventory):
    regions_with_sites(inventory, {"eu-north": ["a"], "eu-south": ["b"]})
    add_site(inventory, "c")

    assert names_in(inventory, "eu") == ["a", "b"]
    assert names_in(inventory, "north") == ["a"]


def test_a_whole_name_wins_when_the_region_has_no_sites(inventory):
    regions_with_sites(inventory, {"eu": [], "eu-north": ["b"]})

    assert names_in(inventory, "eu") == []
    assert names_in(inventory, "eu-n") == ["b"]


def test_the_whole_name_is_compared_ignoring_case(inventory):
    regions_with_sites(inventory, {"eu": ["a"], "eu-north": ["b"]})

    assert names_in(inventory, "EU") == ["a"]
    assert names_in(inventory, "Eu-North") == ["b"]


def test_a_site_in_two_matching_regions_is_listed_once(inventory):
    regions_with_sites(inventory, {"eu-north": ["a", "b"], "eu-south": ["a"]})

    assert names_in(inventory, "eu") == ["a", "b"]


def test_a_name_no_region_has_means_no_sites(inventory):
    regions_with_sites(inventory, {"eu": ["a"]})

    assert names_in(inventory, "asia") == []


def test_the_site_list_takes_a_whole_region_name_exactly(inventory):
    regions_with_sites(inventory, {"eu": ["a"], "eu-north": ["b"]})

    names = lambda region: sorted(s.name for s in run(inventory.sites.query(region=region)).items)  # noqa: E731

    assert names("eu") == ["a"]
    assert names("eu-north") == ["b"]
    assert names("north") == ["b"]


def test_the_logical_node_list_takes_a_whole_region_name_exactly(inventory):
    regions_with_sites(inventory, {"eu": ["a"], "eu-north": ["b"]})
    with Session(inventory.db.connection.engine) as session:
        session.add_all(
            [LogicalNode(hostname="sw-a", role="core", site="a"), LogicalNode(hostname="sw-b", role="core", site="b")]
        )
        session.commit()
    service = LogicalNodeService(
        LogicalNodeAdapter(DatabasePlugin(inventory.db, LogicalNode)),
        config_compiler=None,
        integrations=None,
        db_manager=inventory.db,
    )

    hostnames = lambda region: sorted(n.hostname for n in run(service.query(region=region)).items)  # noqa: E731

    assert hostnames("eu") == ["sw-a"]
    assert hostnames("eu-north") == ["sw-b"]
    assert hostnames("north") == ["sw-b"]


def test_the_node_list_takes_a_whole_region_name_exactly(inventory):
    regions_with_sites(inventory, {"eu": ["a"], "eu-north": ["b"]})
    with Session(inventory.db.connection.engine) as session:
        for hostname, site in (("sw-a", "a"), ("sw-b", "b")):
            logical_node = LogicalNode(hostname=hostname, role="core", site=site, sequence=1)
            asset = Asset(
                vendor="cisco",
                hardware_model="C9300",
                serial_number=f"SN-{hostname}",
                os="cisco_iosxe",
                os_version="17.9",
            )
            session.add_all([logical_node, asset])
            session.flush()
            session.add(Node(asset_ref_id=asset.id, logical_node_id=logical_node.id))
        session.commit()

    def get_asset(asset_id):
        with Session(inventory.db.connection.engine) as session:
            return session.get(Asset, asset_id)

    inventory.assets = SimpleNamespace(adapter=SimpleNamespace(get=get_asset))
    service = NodeService(NodeAdapter(DatabasePlugin(inventory.db, Node)), inventory)

    hostnames = lambda region: sorted(n.hostname for n in run(service.query(region=region)).items)  # noqa: E731

    assert hostnames("eu") == ["sw-a"]
    assert hostnames("eu-north") == ["sw-b"]
    assert hostnames("north") == ["sw-b"]
