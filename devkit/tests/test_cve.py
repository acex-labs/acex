"""CVE API schemas are independent of the SQL table model."""

import json
from datetime import UTC, datetime

import pytest
from acex_devkit.models.cve import CveCreate, CveDiscoverData, CveResponse
from pydantic import ValidationError


def test_create_dates_are_json_compatible_in_standard_dump():
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    payload = CveCreate(
        cve_id="CVE-2026-1234",
        published=timestamp,
        last_modified=timestamp,
        raw={},
    )

    data = json.loads(json.dumps(payload.model_dump()))

    assert data["published"] == timestamp.isoformat()
    assert data["last_modified"] == timestamp.isoformat()
    assert payload.published == timestamp
    assert CveCreate.model_validate(data) == payload


def test_discovery_dates_are_json_compatible_in_standard_dump():
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    payload = CveDiscoverData(start=timestamp, end=timestamp)

    data = json.loads(json.dumps(payload.model_dump()))

    assert data["start"] == timestamp.isoformat()
    assert data["end"] == timestamp.isoformat()
    assert CveDiscoverData.model_validate(data) == payload


def test_optional_create_dates_remain_none():
    payload = CveCreate(cve_id="CVE-2026-1234", raw={})

    assert payload.model_dump()["published"] is None
    assert payload.model_dump()["last_modified"] is None


def test_create_converts_to_table_and_response():
    payload = CveCreate.model_validate(
        {
            "cve_id": "CVE-2000-1027",
            "published": "2000-12-11T05:00:00Z",
            "cvss_score": 5.0,
            "raw": {"id": "CVE-2000-1027"},
        }
    )
    response = CveResponse.model_validate(
        {
            **payload.model_dump(),
            "id": 1,
            "created_at": datetime.now(UTC),
            "updated_at": None,
        }
    )
    assert response.id == 1
    assert response.cve_id == payload.cve_id
    assert response.published == payload.published
    assert response.raw == payload.raw
    assert response.created_at is not None
    assert CveResponse.model_validate_json(response.model_dump_json()) == response


@pytest.mark.parametrize(
    "data",
    [
        {"raw": {}},
        {"cve_id": "CVE-2000-1027"},
        {"cve_id": "CVE-2000-1027", "raw": []},
        {"cve_id": "CVE-2000-1027", "raw": {}, "published": "invalid"},
    ],
)
def test_create_validates_incoming_data(data):
    with pytest.raises(ValidationError):
        CveCreate.model_validate(data)
