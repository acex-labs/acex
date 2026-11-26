"""The actions' shared conventions, and a session running one: a table is cut to the caller's max_entries."""

import asyncio

import pytest
from acex_devkit.drivers import Actions, Session, Transport
from acex_devkit.exceptions import DriverException
from acex_devkit.models.actions import (
    ACTIONS,
    ActionInfo,
    LookupArpResult,
    MacAddressTableParams,
    MacAddressTableResult,
    MacEntry,
    PingParams,
    PingResult,
    TableParams,
    TracerouteResult,
)
from pydantic import ValidationError

ENTRIES = [MacEntry(mac=f"00:00:00:00:00:0{n}", vlan=10, interface="Gi1/0/1", type="dynamic") for n in range(5)]


class NoTransport(Transport):
    async def open(self) -> None: ...

    async def close(self) -> None: ...


class TableActions(Actions):
    async def ping(self, transport: Transport, params: PingParams) -> PingResult:
        return PingResult(sent=params.count, received=params.count)

    async def get_mac_address_table(self, transport: Transport, params: MacAddressTableParams) -> MacAddressTableResult:
        return MacAddressTableResult(entries=ENTRIES)


def session(actions: Actions | None = None) -> Session:
    return Session(NoTransport("10.0.0.1", []), None, actions or TableActions())


@pytest.mark.parametrize("written", ["0050.56A1.2B3C", "00-50-56-a1-2b-3c", "00:50:56:A1:2B:3C", "005056a12b3c"])
def test_a_mac_address_is_read_from_any_common_form(written):
    assert MacEntry(mac=written, interface="Gi1", type="dynamic").mac == "00:50:56:a1:2b:3c"


def test_something_else_is_not_a_mac_address():
    with pytest.raises(ValidationError):
        MacEntry(mac="0050.56a1.2b3", interface="Gi1", type="dynamic")


def test_a_table_is_cut_at_max_entries_and_says_so():
    result = asyncio.run(session().run_action(MacAddressTableParams(max_entries=2)))

    assert (len(result.entries), result.total, result.truncated) == (2, 5, True)


def test_a_table_without_max_entries_is_whole():
    result = asyncio.run(session().run_action(MacAddressTableParams()))

    assert (len(result.entries), result.total, result.truncated) == (5, 5, False)


def test_an_action_that_is_no_table_is_returned_as_is():
    assert asyncio.run(session().run_action(PingParams(target="10.0.0.2", count=3))).success


def test_an_action_the_driver_lacks_is_refused():
    with pytest.raises(DriverException, match="get_arp_table"):
        asyncio.run(session().run_action(ACTIONS["get_arp_table"].params()))


def test_a_driver_reports_the_actions_it_implements():
    assert TableActions.implemented() == ["get_mac_address_table", "ping"]


def test_every_action_is_a_method_of_the_facade_named_as_it():
    assert {name for name in ACTIONS} <= {name for name in dir(Actions) if not name.startswith("_")}


def test_every_table_action_can_be_cut():
    for spec in ACTIONS.values():
        assert issubclass(spec.params, TableParams) == hasattr(spec.result, "limit"), spec.name


def test_a_lookup_and_a_trace_say_whether_they_got_there():
    assert not LookupArpResult(ip="10.0.0.1").found
    assert not TracerouteResult(destination=None, hops=[]).reached


def test_an_action_is_listed_with_its_schemas_and_rows():
    info = ActionInfo.of(ACTIONS["get_mac_address_table"])

    assert (info.label, info.rows) == ("MAC address table", "entries")
    assert info.columns == ["mac", "vlan", "interface", "type"]
    assert set(info.params["properties"]) == {"max_entries", "vlan", "interface"}
    assert "found" not in info.result["properties"]


def test_an_action_without_rows_lists_its_results_fields():
    info = ActionInfo.of(ACTIONS["ping"])

    assert info.rows is None
    assert "success_rate" in info.columns and "success_rate" in info.result["properties"]
