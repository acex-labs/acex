"""An asset on Cisco Business firmware (Catalyst 1300) can be created and listed back."""

import asyncio
from types import SimpleNamespace

import pytest
from acex.database import Connection, DatabaseManager
from acex.inventory.asset_service import AssetService
from acex.models import Asset
from acex.plugins.adaptors.asset_adapter import AssetAdapter
from acex.plugins.integrations.database import DatabasePlugin


@pytest.fixture
def assets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = DatabaseManager(Connection(backend="sqlite", dbname="inventory.db"))
    db.create_tables()
    return AssetService(
        AssetAdapter(DatabasePlugin(db, Asset)), hardware_models=SimpleNamespace(enable_for_asset=lambda *a, **k: None)
    )


def test_a_catalyst_1300_is_created_and_listed_back_with_its_four_number_firmware(assets):
    created = Asset(
        vendor="cisco",
        hardware_model="C1300-48P-4X",
        os="cisco_business",
        os_version="4.1.7.17",
        serial_number="SN-1300-1",
    )

    asyncio.run(assets.create(created))
    listed = asyncio.run(assets.query(os="cisco_business"))

    assert [(a.hardware_model, a.os, a.os_version) for a in listed.items] == [
        ("C1300-48P-4X", "cisco_business", "4.1.7.17")
    ]
