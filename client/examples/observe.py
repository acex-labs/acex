"""Operational example — observe running config and upload to backend.

Run with:  ACEX_BASE_URL=http://acex.local/ python examples/observe.py
"""

from acex_client import Acex
from acex_devkit.models.config_snapshot import DeviceConfigUpload


def main():
    with Acex.from_env() as client:
        node_id = 100

        # In a real scenario this would be fetched from the device via a NED.
        # Here we use a stub for demonstration.
        running_config = "! hostname R1\ninterface Gi0/1\n switchport\n"

        result = client.inventory.node_instances.upload_observed(
            id=node_id,
            payload=DeviceConfigUpload(content=running_config),
        )
        print(f"uploaded snapshot: {result['hash']}")


if __name__ == "__main__":
    main()
