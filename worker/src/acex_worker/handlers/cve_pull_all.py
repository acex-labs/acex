import time
from datetime import datetime, timedelta, timezone
import requests

from acex_client import Acex
from acex_devkit.models.job import JobResponse
from acex_devkit.models.cve import CveDiscoverData
from .base_handler import Handler

from acex_devkit.models.cve import utcnow

BASE_URL = "https://services.nvd.nist.gov/rest/json"
ENDPOINTS = {
    "cve": ("cves/2.0", "vulnerabilities"),
    "cpe": ("cpes/2.0", "products"),
    "cpeMatch": ("cpematch/2.0", "matchStrings"),
    "cveHistory": ("cvehistory/2.0", "cveChanges"),
    "source": ("source/2.0", "sources"),
}

MAX_WINDOW = timedelta(days=119)  # NVD rejects lastMod ranges longer than 120 days
RETRY_STATUS = (429, 500, 502, 503, 504)
PARTS = ("o", "a", "h")  # OS, applications, hardware


# Utility functions
def utcnow():
    return datetime.now(timezone.utc)

# Convert datetime to ISO 8601 string for NVD API queries
def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000+00:00")

# Convert NVD CVE item to API payload dictionary
def to_row(item):
    cve = item["cve"]
    # We are only interested in english language descriptions
    description = next(
        (d["value"] for d in cve.get("descriptions", []) if d["lang"] == "en"), None
    )
    score = None
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        metrics = cve.get("metrics", {}).get(key)
        if metrics:
            score = metrics[0]["cvssData"]["baseScore"]
            break
    return {
        "cve_id": cve["id"],
        "published": datetime.fromisoformat(cve["published"]).replace(
            tzinfo=timezone.utc
        ),
        "last_modified": datetime.fromisoformat(cve["lastModified"]).replace(
            tzinfo=timezone.utc
        ),
        "description": description,
        "cvss_score": score,
        "raw": cve,
        "created_at": utcnow(),
    }

# Agent for interacting with the NVD API
class CveHandler(Handler):
    def __init__(self, api_key: str | None):
        self.api_key = api_key if api_key else None
        self.vendor = "Cisco"

    def _request(self, link, query, attempts=5):
        """GET one NVD page, retrying on stalls and 429/5xx with exponential backoff."""
        headers = {"apiKey": self.api_key}
        for attempt in range(1, attempts + 1):
            try:
                response = requests.get(
                    link, headers=headers, params=query, timeout=(10, 120)
                )
                if response.status_code not in RETRY_STATUS:
                    response.raise_for_status()
                    return response.json()
                error = f"HTTP {response.status_code}"
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as exc:
                error = exc.__class__.__name__
            if attempt == attempts:
                raise RuntimeError(
                    f"NVD request failed after {attempts} attempts: {error}"
                )
            wait = 2**attempt
            print(
                f"Request failed ({error}), retry {attempt}/{attempts - 1} in {wait}s"
            )
            time.sleep(wait)

    # Fetch all pages for a given product and parameters
    def _pages(self, product, params, results_per_page=500):
        """Yield one page of items at a time from an NVD endpoint."""
        path, items_key = ENDPOINTS[product]
        start_index = 0
        while True:
            query = {
                **params,
                "resultsPerPage": results_per_page,
                "startIndex": start_index,
            }
            data = self._request(f"{BASE_URL}/{path}", query)
            page = data[items_key]
            start_index += len(page)
            print(f"Fetched {start_index}/{data['totalResults']} items")
            if page:
                yield page
            if not page or start_index >= data["totalResults"]:
                return
            if self.api_key is None:
                time.sleep(6)  # NVD limit without a key: 5 requests per 30s
            else:
                time.sleep(0.6)  # NVD limit with a key: 50 requests per 30s

    # Sync CVEs for a specific vendor, windowed by time range
    def handle(self, client: Acex, job: JobResponse):
        """Fetch CVEs modified in the last MAX_WINDOW days and return them as rows."""
        data = CveDiscoverData.model_validate(job.data)
        end = utcnow()
        start = end - MAX_WINDOW
        
        #rows = []
        for part in PARTS:
            print(f"{data.vendor}:{part}: {iso(start)} -> {iso(end)}")
            params = {
                "virtualMatchString": f"cpe:2.3:{part}:{data.vendor}",
                "lastModStartDate": iso(start),
                "lastModEndDate": iso(end),
            }
            for page in self._pages("cve", params):
                client.cve.create_cve(page)
                #rows.extend(to_row(cve_item) for cve_item in page)
        #return rows