import logging
import time
from datetime import datetime, timedelta, timezone

import requests

from acex_client import Acex
from acex_devkit.models.cve import CveCreate, CveDiscoverData, CveDiscoverResult
from acex_devkit.models.job import JobResponse
from acex_worker.handlers.base_handler import Handler

BASE_URL = "https://services.nvd.nist.gov/rest/json"
ENDPOINTS = {
    "cve": ("cves/2.0", "vulnerabilities"),
    "cpe": ("cpes/2.0", "products"),
    "cpeMatch": ("cpematch/2.0", "matchStrings"),
    "cveHistory": ("cvehistory/2.0", "cveChanges"),
    "source": ("source/2.0", "sources"),
}

MAX_WINDOW = timedelta(days=119)  # NVD rejects date ranges longer than 120 days
RETRY_STATUS = (429, 500, 502, 503, 504)  # HTTP status codes that trigger a retry
PARTS = ("o", "a", "h")  # OS, applications, hardware
log = logging.getLogger("acex_worker")


def utcnow():
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso(dt):
    return as_utc(dt).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")


def nvd_item_to_cve(item: dict) -> CveCreate:
    cve = item["cve"]
    # Extract the English description only
    description = next(
        (
            entry["value"]
            for entry in cve.get("descriptions", [])
            if entry["lang"] == "en"
        ),
        None,
    )
    score = None
    base_severity = None
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        metrics = cve.get("metrics", {}).get(key)
        if metrics:
            metric = metrics[0]
            cvss_data = metric["cvssData"]
            score = cvss_data["baseScore"]
            base_severity = cvss_data.get("baseSeverity") or metric.get("baseSeverity")
            break

    def parse_date(value: str) -> datetime:
        return as_utc(datetime.fromisoformat(value))

    return CveCreate(
        cve_id=cve["id"],
        published=parse_date(cve["published"]),
        last_modified=parse_date(cve["lastModified"]),
        description=description,
        cvss_score=score,
        base_severity=base_severity,
        raw=cve,
    )


class CveDiscoveryHandler(Handler):
    def _request(self, link: str, query: dict, api_key: str | None, attempts: int = 5) -> dict:
        """GET one NVD page, retrying on stalls and 429/5xx with exponential backoff."""
        headers = {"apiKey": api_key} if api_key else {}
        for attempt in range(1, attempts + 1):
            try:
                response = requests.get(
                    link, headers=headers, params=query, timeout=(10, 120)
                )
                # If the status code is not in the retry list, raise for status and return JSON. Otherwise, prepare to retry.
                if response.status_code not in RETRY_STATUS:
                    response.raise_for_status()
                    return response.json()
                error = f"HTTP {response.status_code}"
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as exc:
                # If a connection error or timeout occurs, capture the exception name for logging and retry.
                error = exc.__class__.__name__
            if attempt == attempts:
                log.error(f"NVD request failed after {attempt} attempts: {error}")
                raise RuntimeError(
                    f"NVD request failed after {attempts} attempts: {error}"
                )
            # exponential backoff before retrying
            wait = 2**attempt
            log.warning(
                f"NVD request failed ({error}); retry {attempt}/{attempts - 1} in {wait}s"
            )
            time.sleep(wait)
        log.error("NVD request retry loop ended unexpectedly")
        raise RuntimeError("NVD request retry loop ended unexpectedly")

    def _pages(self, product: str, params: dict, api_key: str | None, results_per_page: int = 500):
        """Yield one page of items at a time from an NVD endpoint."""
        path, items_key = ENDPOINTS[product]
        start_index = 0
        while True:
            query = {
                **params,
                "resultsPerPage": results_per_page,
                "startIndex": start_index,
            }
            data = self._request(f"{BASE_URL}/{path}", query, api_key)
            page = data[items_key]
            start_index += len(page)
            log.info(f"Fetched {start_index}/{data['totalResults']} {product} items")
            if page:
                yield page
            if not page or start_index >= data["totalResults"]:
                return
            if api_key is None:
                time.sleep(6)  # NVD limit without a key: 5 requests per 30s
            else:
                time.sleep(0.6)  # NVD limit with a key: 50 requests per 30s

    def handle(self, client: Acex, job: JobResponse) -> CveDiscoverResult:
        """Fetch a vendor's CVEs from NVD and batch-store each page in ACE-X."""
        data = CveDiscoverData.model_validate(job.data)
        end = as_utc(data.end) if data.end else utcnow()
        start = as_utc(data.start) if data.start else end - MAX_WINDOW
        if start > end:
            log.error("CVE discovery start must be before or equal to end")
            raise ValueError("CVE discovery start must be before or equal to end")

        api_key = client.cves.api_key.get()
        vendor = data.vendor #or "Cisco"
        if vendor is None:
            log.error("Vendor must be specified")
            raise ValueError("Vendor must be specified")
        discovered_cves: set[str] = set()
        window_start = start
        for part in PARTS:
            window_start = start
            while window_start < end:
                window_end = min(window_start + MAX_WINDOW, end)
                log.info(f"{vendor}:{part}: {iso(window_start)} -> {iso(window_end)}")
                params = {
                    "virtualMatchString": f"cpe:2.3:{part}:{vendor}",
                    "pubStartDate": iso(window_start),
                    "pubEndDate": iso(window_end),
                }
                for page in self._pages("cve", params, api_key):
                    cves = [nvd_item_to_cve(item) for item in page]
                    client.cves.bulk_create(payload=cves)
                    discovered_cves.update(cve.cve_id for cve in cves)
                window_start = window_end

        return CveDiscoverResult(
            vendor=vendor,
            start=start,
            end=end,
            discovered_cves=sorted(discovered_cves),
        )
