#!/usr/bin/env python3
"""
Seed script for local development — populates the database with regions,
sites, region assignments, assets, logical nodes, node instances, and
configuration history.

Config snapshots are read from scripts/configs/{hostname}/*.conf (sorted
alphabetically), so adding a new revision is as simple as dropping another
file in the right directory.

Usage:
    python3 scripts/seed_dev_data.py [--base-url http://localhost:80]
"""

import base64
import json
import urllib.request
import argparse
from pathlib import Path


CONFIGS_DIR = Path(__file__).parent / "configs"


def b64(text):
    return base64.b64encode(text.encode()).decode()


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
            label = resp.get("name") or resp.get("id") or resp.get("hash") or ""
            if isinstance(label, str) and len(label) > 12:
                label = label[:12] + "…"
            print(f"  OK   {method} {path} → {label}")
            return resp
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        print(f"  ERR  {method} {path}: HTTP {e.code} — {body_bytes.decode()[:120]}")
        return None


def get_snapshots(hostname: str) -> list[tuple[str, str]]:
    """Return [(filename, content), …] for all *.conf files under configs/{hostname}/, sorted."""
    node_dir = CONFIGS_DIR / hostname
    if not node_dir.is_dir():
        return []
    return [(p.name, p.read_text()) for p in sorted(node_dir.glob("*.conf"))]


# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

REGIONS = [
    {"name": "EMEA",     "display_name": "Europe, Middle East & Africa"},
    {"name": "APAC",     "display_name": "Asia Pacific"},
    {"name": "Americas", "display_name": "Americas"},
]

# Each site carries a `region` key (removed before POST) used for the assignment.
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

# ned_id=None → server stores raw text without NED processing
ASSETS = [
    # STO-DC1 — Cisco core/distribution + Juniper border-leaf
    {"vendor": "cisco",   "serial_number": "FCZ2042X001", "os": "iosxe",  "os_version": "17.9.4a",   "hardware_model": "Catalyst 9500-40X", "ned_id": "CiscoIOSCLIDriver"},
    {"vendor": "cisco",   "serial_number": "FCZ2042X002", "os": "iosxe",  "os_version": "17.9.4a",   "hardware_model": "Catalyst 9300-48P", "ned_id": "CiscoIOSCLIDriver"},
    {"vendor": "cisco",   "serial_number": "FCZ2042X003", "os": "iosxe",  "os_version": "17.9.4a",   "hardware_model": "Catalyst 9300-48P", "ned_id": "CiscoIOSCLIDriver"},
    {"vendor": "juniper", "serial_number": "VN3721AB001", "os": "junos",  "os_version": "22.4R1.10", "hardware_model": "QFX5120-48Y",      "ned_id": "JunosCLI"},
    # AMS-DC1 — Juniper core/leaf + Cisco OOB management switch
    {"vendor": "juniper", "serial_number": "VN3721AB002", "os": "junos",  "os_version": "22.4R1.10", "hardware_model": "PTX1000",          "ned_id": "JunosCLI"},
    {"vendor": "juniper", "serial_number": "VN3721AB003", "os": "junos",  "os_version": "22.4R1.10", "hardware_model": "QFX5100-48S",      "ned_id": "JunosCLI"},
    {"vendor": "juniper", "serial_number": "VN3721AB004", "os": "junos",  "os_version": "22.4R1.10", "hardware_model": "QFX5100-48S",      "ned_id": "JunosCLI"},
    {"vendor": "cisco",   "serial_number": "FGL2318Y001", "os": "nxos",   "os_version": "10.2.5",    "hardware_model": "Nexus 93180YC-FX", "ned_id": "CiscoIOSCLIDriver"},
]

# asset_idx refers to the position in ASSETS above.
# lldp lists the neighbors each node reports — remote_device is resolved to a
# remote_node_id automatically by the server if the hostname exists in inventory.
NODE_SPECS = [
    # STO-DC1: classic three-tier (core → distribution → border-leaf)
    {
        "hostname": "sto-dc1-core-1", "role": "core", "site": "sto-dc1", "sequence": 1, "asset_idx": 0,
        "lldp": [
            {"local_interface": "GigabitEthernet1/0/2", "remote_device": "sto-dc1-dist-1",     "remote_interface": "GigabitEthernet1/0/1"},
            {"local_interface": "GigabitEthernet1/0/3", "remote_device": "sto-dc1-dist-2",     "remote_interface": "GigabitEthernet1/0/1"},
            {"local_interface": "xe-0/0/48",             "remote_device": "sto-dc1-bdr-leaf-1", "remote_interface": "xe-0/0/0"},
        ],
    },
    {
        "hostname": "sto-dc1-dist-1", "role": "distribution", "site": "sto-dc1", "sequence": 1, "asset_idx": 1,
        "lldp": [
            {"local_interface": "GigabitEthernet1/0/1", "remote_device": "sto-dc1-core-1", "remote_interface": "GigabitEthernet1/0/2"},
        ],
    },
    {
        "hostname": "sto-dc1-dist-2", "role": "distribution", "site": "sto-dc1", "sequence": 2, "asset_idx": 2,
        "lldp": [
            {"local_interface": "GigabitEthernet1/0/1", "remote_device": "sto-dc1-core-1", "remote_interface": "GigabitEthernet1/0/3"},
        ],
    },
    {
        "hostname": "sto-dc1-bdr-leaf-1", "role": "border-leaf", "site": "sto-dc1", "sequence": 1, "asset_idx": 3,
        "lldp": [
            {"local_interface": "xe-0/0/0", "remote_device": "sto-dc1-core-1", "remote_interface": "xe-0/0/48"},
        ],
    },
    # AMS-DC1: spine-leaf (core → leaf × 2) + OOB
    {
        "hostname": "ams-dc1-core-1", "role": "core", "site": "ams-dc1", "sequence": 1, "asset_idx": 4,
        "lldp": [
            {"local_interface": "xe-0/0/0",  "remote_device": "ams-dc1-leaf-1", "remote_interface": "xe-0/0/0"},
            {"local_interface": "xe-0/0/1",  "remote_device": "ams-dc1-leaf-2", "remote_interface": "xe-0/0/0"},
            {"local_interface": "xe-0/0/47", "remote_device": "ams-dc1-oob-1",  "remote_interface": "Ethernet1/1"},
        ],
    },
    {
        "hostname": "ams-dc1-leaf-1", "role": "leaf", "site": "ams-dc1", "sequence": 1, "asset_idx": 5,
        "lldp": [
            {"local_interface": "xe-0/0/0", "remote_device": "ams-dc1-core-1", "remote_interface": "xe-0/0/0"},
        ],
    },
    {
        "hostname": "ams-dc1-leaf-2", "role": "leaf", "site": "ams-dc1", "sequence": 2, "asset_idx": 6,
        "lldp": [
            {"local_interface": "xe-0/0/0", "remote_device": "ams-dc1-core-1", "remote_interface": "xe-0/0/1"},
        ],
    },
    {
        "hostname": "ams-dc1-oob-1", "role": "oob", "site": "ams-dc1", "sequence": 1, "asset_idx": 7,
        "lldp": [
            {"local_interface": "Ethernet1/1", "remote_device": "ams-dc1-core-1", "remote_interface": "xe-0/0/47"},
        ],
    },
]

_LN_API_FIELDS = {"hostname", "role", "site", "sequence"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Seed dev database with regions, sites, assets, logical nodes, node instances, and config history."
    )
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

    print("\n=== Assets ===")
    asset_ids: dict[int, int] = {}
    for i, asset in enumerate(ASSETS):
        resp = post(base, "/api/v1/inventory/assets/", asset)
        if resp:
            asset_ids[i] = resp["id"]

    print("\n=== Logical Nodes ===")
    ln_ids: dict[int, int] = {}
    for i, spec in enumerate(NODE_SPECS):
        body = {k: v for k, v in spec.items() if k in _LN_API_FIELDS}
        resp = post(base, "/api/v1/inventory/logical_nodes/", body)
        if resp:
            ln_ids[i] = resp["id"]

    print("\n=== Node Instances ===")
    node_ids: dict[int, int] = {}
    for i, spec in enumerate(NODE_SPECS):
        a_idx = spec["asset_idx"]
        if a_idx not in asset_ids or i not in ln_ids:
            print(f"  SKIP  {spec['hostname']} — missing asset or logical node")
            continue
        resp = post(base, "/api/v1/inventory/node_instances/", {
            "asset_ref_id": asset_ids[a_idx],
            "asset_ref_type": "asset",
            "logical_node_id": ln_ids[i],
            "status": "active",
        })
        if resp:
            node_ids[i] = resp["id"]

    print("\n=== Configuration History ===")
    for i, spec in enumerate(NODE_SPECS):
        if i not in node_ids:
            print(f"  SKIP  {spec['hostname']} — no node instance")
            continue
        nid = node_ids[i]
        snapshots = get_snapshots(spec["hostname"])
        if not snapshots:
            print(f"  SKIP  {spec['hostname']} — no .conf files in configs/{spec['hostname']}/")
            continue
        print(f"  {spec['hostname']} (node_instance_id={nid}) — {len(snapshots)} snapshot(s)")
        for filename, content in snapshots:
            resp = post(
                base,
                f"/api/v1/inventory/node_instances/{nid}/configuration/observed/",
                {"content": b64(content)},
            )
            if resp:
                h = (resp.get("hash") or "")[:8]
                print(f"    {filename} → {h}…")

    print("\n=== LLDP Neighbors ===")
    for i, spec in enumerate(NODE_SPECS):
        if i not in node_ids or not spec.get("lldp"):
            continue
        nid = node_ids[i]
        resp = post(base, "/api/v1/operations/lldp_neighbors/", {
            "node_instance_id": nid,
            "neighbors": spec["lldp"],
        })
        if resp:
            print(f"    {spec['hostname']} — {resp.get('count', 0)} neighbor(s)")

    print("\nDone.")


if __name__ == "__main__":
    main()
