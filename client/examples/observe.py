"""Operational example — render desired config, observe compliance, upload observed.

Run with:  ACEX_BASE_URL=http://acex.local/ python examples/observe.py
"""

from acex_client import Acex
from acex_devkit.models.config_snapshot import DeviceConfigUpload


def main():
    with Acex.from_env() as client:
        node_id = 1

        # Render the desired configuration (text) via the NED driver
        desired = client.inventory.node_instances.configuration_desired(id=node_id)
        print(f"--- desired config ({len(desired)} bytes) ---")
        print(desired)

        # Compliance summary
        compliance = client.operations.compliance.check(node_instance_id=node_id)
        print(
            f"compliance: {compliance.compliant_count}/{compliance.total_desired} ({compliance.compliance_percentage}%)"
        )

        # Upload an observed running-config snapshot
        running = "! hostname R1\ninterface Gi0/1\n switchport\n"
        result = client.inventory.node_instances.upload_observed(
            id=node_id,
            payload=DeviceConfigUpload(content=running),
        )
        print(f"uploaded snapshot: {result['hash']}")

        # Diff two observed snapshots
        snap_id_a = client.inventory.node_instances.list_observed(id=node_id)[0].id
        snap_id_b = client.inventory.node_instances.list_observed(id=node_id)[-1].id
        diff = client.inventory.node_instances.diff_observed(id=node_id, a=snap_id_a, b=snap_id_b)
        print(f"diff stats: added={diff.stats.added} removed={diff.stats.removed}")


if __name__ == "__main__":
    main()
