#!/usr/bin/env python3
"""
Seed script for local development — populates the database with regions,
sites (real cities with coordinates), and region assignments.

Usage:
    python3 scripts/seed_dev_data.py [--base-url http://localhost:80]
"""

import json
import sys
import urllib.request
import argparse


def post(base, path, body, *, method="POST"):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{base}{path}", data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as r:
            resp = json.loads(r.read())
            label = resp.get("name") or resp.get("id")
            print(f"  OK   {method} {path} → {label}")
            return resp
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        print(f"  ERR  {method} {path}: HTTP {e.code} — {body_bytes.decode()[:120]}")
        return None


def delete(base, path):
    req = urllib.request.Request(f"{base}{path}", method="DELETE")
    try:
        with urllib.request.urlopen(req):
            pass
    except Exception:
        pass


REGIONS = [
    {"name": "EMEA",     "display_name": "Europe, Middle East & Africa"},
    {"name": "APAC",     "display_name": "Asia Pacific"},
    {"name": "Americas", "display_name": "Americas"},
]

# Each site has a `region` key (removed before POST) that drives the assignment.
SITES = [
    # EMEA
    {"name": "sto-dc1", "display_name": "Stockholm DC1",    "city": "Stockholm",    "country": "Sweden",       "latitude":  59.3293, "longitude":  18.0686, "region": "EMEA"},
    {"name": "ams-dc1", "display_name": "Amsterdam DC1",    "city": "Amsterdam",    "country": "Netherlands",  "latitude":  52.3676, "longitude":   4.9041, "region": "EMEA"},
    {"name": "lon-dc1", "display_name": "London DC1",       "city": "London",       "country": "UK",           "latitude":  51.5074, "longitude":  -0.1278, "region": "EMEA"},
    {"name": "fra-dc1", "display_name": "Frankfurt DC1",    "city": "Frankfurt",    "country": "Germany",      "latitude":  50.1109, "longitude":   8.6821, "region": "EMEA"},
    {"name": "par-dc1", "display_name": "Paris DC1",        "city": "Paris",        "country": "France",       "latitude":  48.8566, "longitude":   2.3522, "region": "EMEA"},
    {"name": "dub-dc1", "display_name": "Dubai DC1",        "city": "Dubai",        "country": "UAE",          "latitude":  25.2048, "longitude":  55.2708, "region": "EMEA"},
    {"name": "joh-dc1", "display_name": "Johannesburg DC1", "city": "Johannesburg", "country": "South Africa", "latitude": -26.2041, "longitude":  28.0473, "region": "EMEA"},
    # APAC
    {"name": "sin-dc1", "display_name": "Singapore DC1",   "city": "Singapore",    "country": "Singapore",    "latitude":   1.3521, "longitude": 103.8198, "region": "APAC"},
    {"name": "tok-dc1", "display_name": "Tokyo DC1",        "city": "Tokyo",        "country": "Japan",        "latitude":  35.6762, "longitude": 139.6503, "region": "APAC"},
    {"name": "syd-dc1", "display_name": "Sydney DC1",       "city": "Sydney",       "country": "Australia",    "latitude": -33.8688, "longitude": 151.2093, "region": "APAC"},
    {"name": "hkg-dc1", "display_name": "Hong Kong DC1",   "city": "Hong Kong",    "country": "China",        "latitude":  22.3193, "longitude": 114.1694, "region": "APAC"},
    {"name": "mum-dc1", "display_name": "Mumbai DC1",       "city": "Mumbai",       "country": "India",        "latitude":  19.0760, "longitude":  72.8777, "region": "APAC"},
    # Americas
    {"name": "nyc-dc1", "display_name": "New York DC1",    "city": "New York",     "country": "USA",          "latitude":  40.7128, "longitude": -74.0060, "region": "Americas"},
    {"name": "lax-dc1", "display_name": "Los Angeles DC1", "city": "Los Angeles",  "country": "USA",          "latitude":  34.0522, "longitude":-118.2437, "region": "Americas"},
    {"name": "chi-dc1", "display_name": "Chicago DC1",     "city": "Chicago",      "country": "USA",          "latitude":  41.8781, "longitude": -87.6298, "region": "Americas"},
    {"name": "sao-dc1", "display_name": "São Paulo DC1",   "city": "São Paulo",    "country": "Brazil",       "latitude": -23.5505, "longitude": -46.6333, "region": "Americas"},
    {"name": "tor-dc1", "display_name": "Toronto DC1",     "city": "Toronto",      "country": "Canada",       "latitude":  43.6532, "longitude": -79.3832, "region": "Americas"},
    {"name": "bog-dc1", "display_name": "Bogotá DC1",      "city": "Bogotá",       "country": "Colombia",     "latitude":   4.7110, "longitude": -74.0721, "region": "Americas"},
]


def main():
    parser = argparse.ArgumentParser(description="Seed dev database with regions, sites, and region assignments.")
    parser.add_argument("--base-url", default="http://localhost:80", help="API base URL")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print(f"\nSeeding {base}\n")

    print("=== Regions ===")
    for r in REGIONS:
        post(base, "/api/v1/inventory/regions/", r)

    print("\n=== Sites ===")
    site_region_map = {}
    for s in SITES:
        region = s.pop("region")
        resp = post(base, "/api/v1/inventory/sites/", s)
        if resp:
            site_region_map[s["name"]] = region
        s["region"] = region  # restore for re-runs

    print("\n=== Region assignments ===")
    for site_name, region_name in site_region_map.items():
        post(base, "/api/v1/inventory/region_assignments/", {
            "site_name": site_name,
            "region_name": region_name,
        })

    print("\nDone.")


if __name__ == "__main__":
    main()
