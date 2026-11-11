"""Tests for the compliance resource via respx mocks."""

from __future__ import annotations

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.http import RestClient
from acex_client.resources.compliance import Compliance
from httpx import Response

MEASURED = {
    "status": "measured",
    "total_desired": 10,
    "total_observed": 12,
    "compliant_count": 9,
    "undeclared_count": 3,
    "unparsed_count": 1,
    "compliance_percentage": 90.0,
}
NOT_COLLECTED = {"status": "not_collected", "compliance_percentage": None}
SOFTWARE = {
    "assets_total": 1,
    "golden_count": 1,
    "compliance_percentage": 100.0,
    "assets": [
        {
            "asset_id": 7,
            "hardware_model": "C9300-24T",
            "os": "cisco_iosxe",
            "os_version": "17.9.4a",
            "status": "golden",
            "golden_version": "17.9.4a",
        }
    ],
}
SUMMARY = {
    "configuration": {
        "nodes_total": 2,
        "nodes_not_collected": 1,
        "total_desired": 10,
        "compliant_count": 9,
        "compliance_percentage": 90.0,
    },
    "software": {"assets_total": 2, "golden_count": 1, "not_allowed_count": 1, "compliance_percentage": 50.0},
}


@pytest.fixture
def compliance():
    rest = RestClient("http://test/api/v1", NullAuthProvider(), timeout=5.0)
    try:
        yield Compliance(rest)
    finally:
        rest.close()


@respx.mock
def test_node(compliance):
    respx.get("http://test/api/v1/compliance/nodes/1").mock(
        return_value=Response(200, json={"configuration": MEASURED, "software": SOFTWARE})
    )
    result = compliance.node(node_instance_id=1)
    assert result.configuration.compliance_percentage == 90.0
    assert result.configuration.undeclared_count == 3
    assert result.software.assets[0].status == "golden"


@respx.mock
def test_a_node_not_collected_has_no_percentage(compliance):
    respx.get("http://test/api/v1/compliance/nodes/2").mock(
        return_value=Response(200, json={"configuration": NOT_COLLECTED, "software": SOFTWARE})
    )
    result = compliance.node(node_instance_id=2)
    assert result.configuration.status == "not_collected"
    assert result.configuration.compliance_percentage is None


@respx.mock
def test_site(compliance):
    respx.get("http://test/api/v1/compliance/sites/stockholm").mock(
        return_value=Response(
            200,
            json={
                "summary": SUMMARY,
                "nodes": {
                    "1": {"configuration": MEASURED, "software": SOFTWARE},
                    "2": {"configuration": NOT_COLLECTED, "software": SOFTWARE},
                },
            },
        )
    )
    result = compliance.site(site_name="stockholm")
    assert set(result.nodes) == {1, 2}
    assert result.summary.configuration.nodes_not_collected == 1


@respx.mock
def test_region(compliance):
    respx.get("http://test/api/v1/compliance/regions/nordics").mock(
        return_value=Response(200, json={"summary": SUMMARY, "sites": {"stockholm": SUMMARY}})
    )
    result = compliance.region(region_name="nordics")
    assert result.sites["stockholm"].configuration.compliance_percentage == 90.0


@respx.mock
def test_overview(compliance):
    respx.get("http://test/api/v1/compliance").mock(
        return_value=Response(
            200, json={"summary": SUMMARY, "sites": {"stockholm": SUMMARY}, "regions": {"nordics": SUMMARY}}
        )
    )
    result = compliance.overview()
    assert result.summary.configuration.total_desired == 10
    assert result.regions["nordics"].software.compliance_percentage == 50.0
