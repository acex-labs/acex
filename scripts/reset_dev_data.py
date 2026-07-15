#!/usr/bin/env python3
"""
Reset script — deletes all inventory data in reverse dependency order.

Deletion order:
  node instances → logical nodes → assets →
  region assignments → sites → regions

Note: observed config snapshots (device_config table) have no delete
endpoint; they are orphaned when node instances are removed and will
be cleaned up if the database is reset directly.

Usage:
    python3 scripts/reset_dev_data.py [--base-url http://localhost:80]
    python3 scripts/reset_dev_data.py --yes   # skip confirmation prompt
"""

import json
import sys
import urllib.request
import urllib.error
import argparse


def get_all(base, path, limit=1000):
    url = f"{base}{path}?limit={limit}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as r:
            resp = json.loads(r.read())
            items = resp.get("items", resp) if isinstance(resp, dict) else resp
            return items if isinstance(items, list) else []
    except urllib.error.HTTPError as e:
        print(f"  ERR  GET {path}: HTTP {e.code}")
        return []
    except Exception as e:
        print(f"  ERR  GET {path}: {e}")
        return []


def delete(base, path):
    req = urllib.request.Request(f"{base}{path}", method="DELETE")
    try:
        with urllib.request.urlopen(req):
            print(f"  OK   DELETE {path}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  ERR  DELETE {path}: HTTP {e.code}")
        return False


def delete_all(base, list_path, delete_prefix, label):
    items = get_all(base, list_path)
    if not items:
        print(f"  (none)")
        return
    for item in items:
        delete(base, f"{delete_prefix}/{item['id']}")


def main():
    parser = argparse.ArgumentParser(description="Delete all inventory data from the dev database.")
    parser.add_argument("--base-url", default="http://localhost:80", help="API base URL")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    if not args.yes:
        print(f"\nThis will delete ALL inventory data from {base}.")
        answer = input("Type 'yes' to continue: ").strip().lower()
        if answer != "yes":
            print("Aborted.")
            sys.exit(0)

    print(f"\nResetting {base}\n")

    print("=== Node Instances ===")
    delete_all(base, "/api/v1/inventory/node_instances/", "/api/v1/inventory/node_instances", "node instance")

    print("\n=== Logical Nodes ===")
    delete_all(base, "/api/v1/inventory/logical_nodes/", "/api/v1/inventory/logical_nodes", "logical node")

    print("\n=== Assets ===")
    delete_all(base, "/api/v1/inventory/assets/", "/api/v1/inventory/assets", "asset")

    print("\n=== Region Assignments ===")
    delete_all(base, "/api/v1/inventory/region_assignments/", "/api/v1/inventory/region_assignments", "region assignment")

    print("\n=== Sites ===")
    delete_all(base, "/api/v1/inventory/sites/", "/api/v1/inventory/sites", "site")

    print("\n=== Regions ===")
    delete_all(base, "/api/v1/inventory/regions/", "/api/v1/inventory/regions", "region")

    print("\nDone.")


if __name__ == "__main__":
    main()
