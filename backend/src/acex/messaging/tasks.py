import socket
import time
from datetime import UTC, datetime

from acex.messaging.celery_app import celery_app

PROVISION_STAGES = ("bootstrapping", "provisioning", "verifying")


@celery_app.task(name="acex.ping")
def ping() -> dict:
    return {"worker": socket.gethostname(), "ts": datetime.now(UTC).isoformat()}


@celery_app.task(name="acex.provision.node", bind=True)
def provision_node(self, node_instance_id: int, seconds_per_stage: float = 1.0) -> dict:
    """Stand-in for the real provisioning flow: reports each stage as progress."""
    for stage in PROVISION_STAGES:
        self.update_state(state="PROGRESS", meta={"node_instance_id": node_instance_id, "stage": stage})
        time.sleep(seconds_per_stage)
    return {"node_instance_id": node_instance_id, "status": "provisioned"}
