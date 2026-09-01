#!/usr/bin/env python3
"""Seed the minimal inventory chain for the docker-compose mock devices.

Creates (idempotently): collection agent "default", a shared admin/admin
credential, and for each mock router: asset -> logical node -> node instance
-> management connection -> node credential -> agent node link.

Config via env: ACEX_API_URL, ACEX_CLIENT_ID, ACEX_CLIENT_SECRET,
ACEX_ISSUER_URL (matches the agent services in docker-compose.yml).
"""

import os
import sys
import time

from acex_client import Acex
from acex_client.auth import create_auth_provider

API_URL = os.environ.get("ACEX_API_URL", "http://localhost:8080")
AGENT_NAME = "default"

MOCK_ROUTERS = [
    {"hostname": "mock-router-1", "serial_number": "MOCK-ROUTER-1", "target_ip": "mock-router-1"},
    {"hostname": "mock-router-2", "serial_number": "MOCK-ROUTER-2", "target_ip": "mock-router-2"},
]


def make_client() -> Acex:
    """Build an authenticated client, retrying while backend/keycloak come up."""
    for attempt in range(30):
        try:
            return Acex(base_url=API_URL, verify=False)
        except Exception as e:
            if attempt == 29:
                raise
            print(f"  waiting for API ({e}), retrying in 2s...")
            time.sleep(2)
    raise RuntimeError("unreachable")


def get_or_create(resource, match_field, match_value, body):
    """Reuse an existing row matched by a unique field, else create it."""
    existing = resource.query(**{match_field: match_value})
    if existing:
        item = existing.items[0]
        print(f"  =    reuse id={item.id} ({match_value})")
        return item
    item = resource.create(**body)
    print(f"  +    created id={item.id} ({match_value})")
    return item


def main():
    print(f"Seeding mock devices against {API_URL}")
    client = make_client()

    # Collection agent the collection-agent service connects as (COLLECTION_AGENT_ID).
    agent = get_or_create(
        client.inventory.collection_agents,
        "name", AGENT_NAME,
        {"name": AGENT_NAME, "description": "Default dev collection agent", "interval_seconds": 60},
    )
    print(f"Collection agent id={agent.id} (set COLLECTION_AGENT_ID to this)")

    # Shared userpass credential for the mock SSH servers (admin/admin).
    cred = get_or_create(
        client.inventory.credentials,
        "name", "mock-device-admin",
        {"name": "mock-device-admin", "credential_type": "userpass",
         "fields": {"username": "admin", "password": "admin"}},
    )

    for spec in MOCK_ROUTERS:
        print(f"--- {spec['hostname']} ---")
        asset = get_or_create(
            client.inventory.assets,
            "serial_number", spec["serial_number"],
            {"vendor": "cisco", "serial_number": spec["serial_number"], "os": "iosxe",
             "os_version": "17.9.4a", "hardware_model": "Mock Router", "ned_id": "CiscoIOSCLIDriver"},
        )
        ln = get_or_create(
            client.inventory.logical_nodes,
            "hostname", spec["hostname"],
            {"hostname": spec["hostname"], "role": "router"},
        )
        node = get_or_create(
            client.inventory.node_instances,
            "logical_node_id", ln.id,
            {"asset_ref_id": asset.id, "asset_ref_type": "asset",
             "logical_node_id": ln.id, "status": "active"},
        )

        # Management connection: how the agent reaches the device (compose DNS name).
        # NOTE: raw rest.request — the client's ManagementConnectionCreate model
        # drops node_id (backend requires it in the body). Client contract bug.
        if not client.inventory.management_connections.query(node_id=node.id):
            data = client.rest.request(
                "POST",
                "/inventory/management_connections/",
                json={
                    "node_id": node.id,
                    "target_ip": spec["target_ip"],
                    "connection_type": "ssh",
                    "primary": True,
                },
            )
            print(f"  +    mgmt connection id={data['id']} ({spec['target_ip']})")
        else:
            print(f"  =    reuse mgmt connection ({spec['target_ip']})")

        # Attach credential + agent membership (both endpoints tolerate re-runs
        # poorly, so guard by listing first).
        existing_creds = client.inventory.node_credentials(node.id).query()
        if not any(c.credential_id == cred.id for c in existing_creds):
            client.inventory.node_credentials(node.id).create(credential_id=cred.id)
            print("  +    credential attached")
        else:
            print("  =    credential already attached")

        agent_fresh = client.inventory.collection_agents.get(id=agent.id)
        if node.id not in agent_fresh.nodes:
            client.inventory.collection_agents.add_node(id=agent.id, node_id=node.id)
            print(f"  +    linked to agent {agent.id}")
        else:
            print(f"  =    already linked to agent {agent.id}")

    print("Done.")


if __name__ == "__main__":
    sys.exit(main())