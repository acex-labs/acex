#!/usr/bin/env python3
"""Seed the minimal inventory chain for the docker-compose mock devices.

Creates (idempotently):
  - collection agent "default"
  - telemetry agent "default" with SNMP + ICMP capabilities
  - shared SSH credential (admin/admin) and SNMP community (public)
  - for each mock device: asset -> logical node -> node instance
    -> management connection -> credentials -> collection agent link
    -> telemetry agent link
  - writes COLLECTION_AGENT_ID and TELEMETRY_AGENT_ID back to .env

Config via env: ACEX_API_URL, ACEX_CLIENT_ID, ACEX_CLIENT_SECRET,
ACEX_ISSUER_URL (matches the agent services in docker-compose.yml).
"""

import os
import pathlib
import re
import sys
import time

from acex_client import Acex

API_URL   = os.environ.get("ACEX_API_URL", "http://localhost:8080")
ENV_FILE  = pathlib.Path(os.environ.get("ENV_FILE", "/env/.env"))

MOCK_DEVICES = [
    {"hostname": "mock-router-1", "serial_number": "MOCK-ROUTER-1", "target_ip": "mock-router-1", "role": "router", "model": "Mock Router"},
    {"hostname": "mock-router-2", "serial_number": "MOCK-ROUTER-2", "target_ip": "mock-router-2", "role": "router", "model": "Mock Router"},
    {"hostname": "mock-switch-1", "serial_number": "MOCK-SWITCH-1", "target_ip": "mock-switch-1", "role": "switch", "model": "Mock Switch"},
    {"hostname": "mock-switch-2", "serial_number": "MOCK-SWITCH-2", "target_ip": "mock-switch-2", "role": "switch", "model": "Mock Switch"},
    {"hostname": "mock-switch-3", "serial_number": "MOCK-SWITCH-3", "target_ip": "mock-switch-3", "role": "switch", "model": "Mock Switch"},
    {"hostname": "mock-switch-4", "serial_number": "MOCK-SWITCH-4", "target_ip": "mock-switch-4", "role": "switch", "model": "Mock Switch"},
]


def make_client() -> Acex:
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
    existing = resource.query(**{match_field: match_value})
    if existing:
        item = existing.items[0]
        print(f"  =  reuse  id={item.id} ({match_value})")
        return item
    item = resource.create(**body)
    print(f"  +  create id={item.id} ({match_value})")
    return item


def patch_env(key: str, value: str) -> None:
    """Write key=value into .env, replacing existing line or appending."""
    if not ENV_FILE.exists():
        return
    text = ENV_FILE.read_text()
    pattern = rf"^{re.escape(key)}=.*$"
    replacement = f"{key}={value}"
    if re.search(pattern, text, flags=re.MULTILINE):
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + f"\n{replacement}\n"
    ENV_FILE.write_text(text)
    print(f"  .env  {key}={value}")


def main():
    print(f"Seeding mock devices against {API_URL}")
    client = make_client()

    # ── Collection agent ──────────────────────────────────────────────────────
    print("\n[collection agent]")
    coll_agent = get_or_create(
        client.inventory.collection_agents,
        "name", "default",
        {"name": "default", "description": "Default dev collection agent", "interval_seconds": 60},
    )
    patch_env("COLLECTION_AGENT_ID", str(coll_agent.id))

    # ── SSH credential ────────────────────────────────────────────────────────
    print("\n[credentials]")
    ssh_cred = get_or_create(
        client.inventory.credentials,
        "name", "mock-device-admin",
        {"name": "mock-device-admin", "credential_type": "userpass",
         "fields": {"username": "admin", "password": "admin"}},
    )

    # SNMP v2c community credential (used by the telemetry agent)
    snmp_cred = get_or_create(
        client.inventory.credentials,
        "name", "mock-snmp-public",
        {"name": "mock-snmp-public", "credential_type": "snmp_community",
         "fields": {"community": "public"}},
    )

    # ── Telemetry agent ───────────────────────────────────────────────────────
    print("\n[telemetry agent]")
    telem_agent = get_or_create(
        client.observability.agents,
        "name", "default",
        {
            "name": "default",
            "description": "Default dev telemetry agent",
            "capabilities": ["snmp", "icmp"],
            "snmp_version": "2c",
            "snmpv2c_credential_id": snmp_cred.id,
        },
    )
    patch_env("TELEMETRY_AGENT_ID", str(telem_agent.id))

    # ── Devices ───────────────────────────────────────────────────────────────
    for spec in MOCK_DEVICES:
        print(f"\n[{spec['hostname']}]")

        asset = get_or_create(
            client.inventory.assets,
            "serial_number", spec["serial_number"],
            {"vendor": "cisco", "serial_number": spec["serial_number"], "os": "iosxe",
             "os_version": "17.9.4a", "hardware_model": spec["model"], "ned_id": "CiscoIOSCLIDriver"},
        )
        ln = get_or_create(
            client.inventory.logical_nodes,
            "hostname", spec["hostname"],
            {"hostname": spec["hostname"], "role": spec["role"]},
        )
        node = get_or_create(
            client.inventory.node_instances,
            "logical_node_id", ln.id,
            {"asset_ref_id": asset.id, "asset_ref_type": "asset",
             "logical_node_id": ln.id, "status": "active"},
        )

        # Management connection (SSH — used by the collection agent)
        if not client.inventory.management_connections.query(node_id=node.id):
            data = client.rest.request(
                "POST", "/inventory/management_connections/",
                json={"node_id": node.id, "target_ip": spec["target_ip"],
                      "connection_type": "ssh", "primary": True},
            )
            print(f"  +  create mgmt connection id={data['id']}")
        else:
            print(f"  =  reuse  mgmt connection ({spec['target_ip']})")

        # SSH credential
        existing_creds = client.inventory.node_credentials(node.id).query()
        if not any(c.credential_id == ssh_cred.id for c in existing_creds):
            client.inventory.node_credentials(node.id).create(credential_id=ssh_cred.id)
            print("  +  SSH credential attached")
        else:
            print("  =  SSH credential already attached")

        # Collection agent membership
        coll_fresh = client.inventory.collection_agents.get(id=coll_agent.id)
        if node.id not in coll_fresh.nodes:
            client.inventory.collection_agents.add_node(id=coll_agent.id, node_id=node.id)
            print(f"  +  linked to collection agent")
        else:
            print(f"  =  already linked to collection agent")

        # Telemetry agent membership
        telem_fresh = client.observability.agents.get(id=telem_agent.id)
        if node.id not in telem_fresh.nodes:
            client.observability.agents.add_node(id=telem_agent.id, node_id=node.id)
            print(f"  +  linked to telemetry agent")
        else:
            print(f"  =  already linked to telemetry agent")

    print("\nDone.")


if __name__ == "__main__":
    sys.exit(main())
