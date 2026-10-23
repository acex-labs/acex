"""CVE API schemas are independent of the SQL table model."""

import pytest
from pydantic import ValidationError

from acex_devkit.models.cve import CveCreate, CveModel, CveResponse


def test_create_converts_to_table_and_response():
    payload = CveCreate.model_validate(
        {
            "cve_id": "CVE-2000-1027",
            "published": "2000-12-11T05:00:00Z",
            "cvss_score": 5.0,
            "raw": {"id": "CVE-2000-1027"},
        }
    )
    row = CveModel.model_validate(payload)

    assert row.id is None
    assert row.created_at is not None
    assert row.updated_at is None
    row.id = 1

    response = CveResponse.model_validate(row)
    assert response.id == 1
    assert response.cve_id == payload.cve_id
    assert response.published == payload.published
    assert response.raw == payload.raw
    assert response.created_at == row.created_at
    assert CveResponse.model_validate_json(response.model_dump_json()) == response


def test_create_excludes_database_managed_fields():
    payload = CveCreate.model_validate(
        {
            "id": 123,
            "cve_id": "CVE-2000-1027",
            "raw": {},
            "created_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
        }
    )

    assert not {"id", "created_at", "updated_at"} & payload.model_dump().keys()
    assert "id" not in CveCreate.model_json_schema()["properties"]


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
