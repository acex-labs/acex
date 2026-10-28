from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from acex_devkit.models.job import JobResponse
from acex_worker.handlers.cve_discovery import (
    CveDiscoveryHandler,
    nvd_item_to_cve,
)

JOB = JobResponse.model_validate(
    {
        "id": 12,
        "type": "acex.cve.discover",
        "data": {
            "vendor": "Cisco",
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T00:00:00Z",
        },
        "state": "running",
        "created_by": "system",
        "created_at": "2026-01-01T00:00:00Z",
    }
)


def nvd_item(cve_id: str = "CVE-2026-1234") -> dict:
    return {
        "cve": {
            "id": cve_id,
            "published": "2026-01-01T01:00:00+01:00",
            "lastModified": "2026-01-01T00:00:00Z",
            "descriptions": [{"lang": "en", "value": "Example vulnerability"}],
            "metrics": {
                "cvssMetricV31": [{"cvssData": {"baseScore": 8.1, "baseSeverity": "HIGH"}}],
            },
        }
    }


def test_nvd_item_is_normalized_to_the_backend_create_schema():
    result = nvd_item_to_cve(nvd_item())

    assert result.cve_id == "CVE-2026-1234"
    assert result.published == datetime(2026, 1, 1, tzinfo=UTC)
    assert result.last_modified == datetime(2026, 1, 1, tzinfo=UTC)
    assert result.description == "Example vulnerability"
    assert result.cvss_score == 8.1
    assert result.base_severity == "HIGH"
    assert result.raw["id"] == "CVE-2026-1234"


def test_nvd_v2_severity_is_read_from_metric():
    item = nvd_item()
    item["cve"]["metrics"] = {
        "cvssMetricV2": [
            {
                "cvssData": {"baseScore": 7.5},
                "baseSeverity": "HIGH",
            }
        ]
    }

    result = nvd_item_to_cve(item)

    assert result.cvss_score == 7.5
    assert result.base_severity == "HIGH"


def test_discovery_bulk_creates_each_page_and_returns_job_result(monkeypatch):
    handler = CveDiscoveryHandler()
    pages = []

    def fetch_pages(product, params, api_key):
        assert api_key == "backend-key"
        pages.append((product, params))
        return iter([[nvd_item()]])

    stored_batches = []
    monkeypatch.setattr(handler, "_pages", fetch_pages)
    monkeypatch.setattr("acex_worker.handlers.cve_discovery.time.sleep", lambda _seconds: None)
    client = SimpleNamespace(
        cves=SimpleNamespace(
            api_key=SimpleNamespace(get=Mock(return_value="backend-key")),
            bulk_create=lambda payload: stored_batches.append(payload),
        )
    )

    result = handler.handle(client, JOB)

    client.cves.api_key.get.assert_called_once_with()
    assert len(pages) == 3
    assert [params["virtualMatchString"] for _, params in pages] == [
        "cpe:2.3:o:Cisco",
        "cpe:2.3:a:Cisco",
        "cpe:2.3:h:Cisco",
    ]
    assert all(
        params["pubStartDate"] == "2026-01-01T00:00:00.000+00:00"
        and params["pubEndDate"] == "2026-01-02T00:00:00.000+00:00"
        and "lastModStartDate" not in params
        and "lastModEndDate" not in params
        for _, params in pages
    )
    assert len(stored_batches) == 3
    assert all(len(batch) == 1 and batch[0].cve_id == "CVE-2026-1234" for batch in stored_batches)
    assert result.vendor == "Cisco"
    assert result.start == datetime(2026, 1, 1, tzinfo=UTC)
    assert result.end == datetime(2026, 1, 2, tzinfo=UTC)
    assert result.discovered_cves == ["CVE-2026-1234"]


def test_discovery_splits_large_ranges_to_nvd_accepted_windows(monkeypatch):
    handler = CveDiscoveryHandler()
    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=240)
    job = JobResponse.model_validate(
        {
            **JOB.model_dump(mode="json"),
            "data": {"vendor": "Cisco", "start": start, "end": end},
        }
    )
    windows = []
    monkeypatch.setattr(handler, "_pages", lambda _product, params, _api_key: windows.append(params) or iter(()))

    handler.handle(SimpleNamespace(cves=SimpleNamespace(api_key=SimpleNamespace(get=lambda: None))), job)

    assert len(windows) == 9
    assert all(
        datetime.fromisoformat(params["pubEndDate"]) - datetime.fromisoformat(params["pubStartDate"])
        <= timedelta(days=119)
        for params in windows
    )


@pytest.mark.parametrize("key, delay", [("backend-key", 0.6), (None, 6)])
def test_pagination_uses_the_fetched_key_for_headers_and_rate_limit(monkeypatch, key, delay):
    handler = CveDiscoveryHandler()
    get = Mock(
        side_effect=[
            SimpleNamespace(
                status_code=200,
                raise_for_status=lambda: None,
                json=lambda: {
                    "vulnerabilities": [nvd_item()],
                    "totalResults": 2,
                },
            ),
            SimpleNamespace(
                status_code=200,
                raise_for_status=lambda: None,
                json=lambda: {
                    "vulnerabilities": [nvd_item("CVE-2026-5678")],
                    "totalResults": 2,
                },
            ),
        ]
    )
    sleep = Mock()
    monkeypatch.setattr("acex_worker.handlers.cve_discovery.requests.get", get)
    monkeypatch.setattr("acex_worker.handlers.cve_discovery.time.sleep", sleep)

    pages = list(handler._pages("cve", {}, key))

    assert len(pages) == 2
    assert [call.kwargs["params"]["startIndex"] for call in get.call_args_list] == [0, 1]
    assert all(call.kwargs["headers"] == ({"apiKey": key} if key else {}) for call in get.call_args_list)
    sleep.assert_called_once_with(delay)


def test_discovery_does_not_hide_backend_key_fetch_errors(monkeypatch):
    handler = CveDiscoveryHandler()
    fetch_pages = Mock()
    monkeypatch.setattr(handler, "_pages", fetch_pages)
    client = SimpleNamespace(
        cves=SimpleNamespace(
            api_key=SimpleNamespace(get=Mock(side_effect=RuntimeError("Backend unavailable"))),
        )
    )

    with pytest.raises(RuntimeError, match="Backend unavailable"):
        handler.handle(client, JOB)

    fetch_pages.assert_not_called()


def test_request_preserves_key_when_retrying(monkeypatch):
    get = Mock(
        side_effect=[
            requests.exceptions.Timeout(),
            SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"ok": True}),
        ]
    )
    monkeypatch.setattr("acex_worker.handlers.cve_discovery.requests.get", get)
    monkeypatch.setattr("acex_worker.handlers.cve_discovery.time.sleep", lambda _seconds: None)

    assert CveDiscoveryHandler()._request("https://nvd.example", {}, "backend-key") == {"ok": True}
    assert get.call_count == 2
    assert all(call.kwargs["headers"] == {"apiKey": "backend-key"} for call in get.call_args_list)
