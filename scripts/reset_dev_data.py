#!/usr/bin/env python3
"""
Reset script — deletes all inventory and operations data in reverse dependency order.

Discovers everything via the client's list endpoints and deletes it. Safe to
run repeatedly; idempotent. After reset, run seed_dev_data.py for a fresh start.

Note: Observed config snapshots and LLDP neighbors have no delete endpoints;
they are orphaned when node instances are removed and are cleaned up if the
database is reset directly.

Usage:
    python3 scripts/reset_dev_data.py [--base-url http://localhost:80]
    python3 scripts/reset_dev_data.py --yes   # skip confirmation prompt
"""

import argparse
import sys

from acex_client import Acex
from acex_client.auth import NullAuthProvider


def delete_all(resource, label):
    """List all items via query() and delete each by id."""
    items = resource.query(limit=10000)
    if not items:
        print(f"  (none) {label}")
        return
    for item in items:
        try:
            resource.delete(item.id)
            print(f"  OK   DELETE {label}/{item.id}")
        except Exception as e:
            print(f"  ERR  DELETE {label}/{item.id}: {e}")


def delete_all_assignments(resource, label):
    """For assignment resources that use compound keys, delete by id."""
    items = resource.query(limit=10000)
    if not items:
        print(f"  (none) {label}")
        return
    for item in items:
        try:
            resource.delete(item.id)
            print(f"  OK   DELETE {label}/{item.id}")
        except Exception as e:
            print(f"  ERR  DELETE {label}/{item.id}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Delete all data from the dev database.")
    parser.add_argument("--base-url", default="http://localhost:80", help="API base URL")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    if not args.yes:
        print(f"\nThis will delete ALL data from {args.base_url}.")
        answer = input("Type 'yes' to continue: ").strip().lower()
        if answer != "yes":
            print("Aborted.")
            sys.exit(0)

    print(f"\nResetting {args.base_url}\n")

    client = Acex(base_url=args.base_url, auth=NullAuthProvider(), verify=False)

    # Delete in reverse dependency order:
    # node instances → logical nodes → asset clusters → assets →
    # management connections → credentials → contacts → contact assignments →
    # region assignments → observability agents → collection agents →
    # sites → regions

    print("=== Node Instances ===")
    delete_all(client.inventory.node_instances, "node_instances")

    print("\n=== Logical Nodes ===")
    delete_all(client.inventory.logical_nodes, "logical_nodes")

    print("\n=== Asset Clusters ===")
    delete_all(client.inventory.asset_clusters, "asset_clusters")

    print("\n=== Assets ===")
    delete_all(client.inventory.assets, "assets")

    print("\n=== Management Connections ===")
    delete_all(client.inventory.management_connections, "management_connections")

    print("\n=== Credentials ===")
    delete_all(client.inventory.credentials, "credentials")

    print("\n=== Contact Assignments ===")
    delete_all_assignments(client.inventory.contact_assignments, "contact_assignments")

    print("\n=== Contacts ===")
    delete_all(client.inventory.contacts, "contacts")

    print("\n=== Region Assignments ===")
    delete_all_assignments(client.inventory.region_assignments, "region_assignments")

    print("\n=== Observability Agents ===")
    delete_all(client.observability.agents, "observability/agents")

    print("\n=== Collection Agents ===")
    delete_all(client.inventory.collection_agents, "collection_agents")

    print("\n=== Sites ===")
    delete_all(client.inventory.sites, "sites")

    print("\n=== Regions ===")
    delete_all(client.inventory.regions, "regions")

    print("\nDone.")


if __name__ == "__main__":
    main()
