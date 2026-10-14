"""ZTP pipeline: a node is in ZTP while it is enrolled, provisioning or failed.
An enrolled node's stage comes from its asset — whether its device has been
discovered and its identity approved. ZTP can always be cancelled, back to the
status the node had when it was enrolled."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from acex.api.routers.ztp_nodes import create_router as nodes_router
from acex.models import Node
from acex.models.job import Job, JobState
from acex.models.management_connections import ManagementConnection
from acex.models.node import NodeProvisionStatus
from acex.models.ztp_discovery import ZtpDiscovery
from acex.ztp import ZtpDiscoveryManager, ZtpPipelineManager
from sqlmodel import Session, select
from test_ztp_review import _Ztp

NODES = "/api/v1/ztp_nodes"
ENROLLED = NodeProvisionStatus.enrolled


@pytest.fixture
def ztp():
    return _Ztp()


@pytest.fixture
def client(ztp):
    pipeline = ZtpPipelineManager(ztp.db, ZtpDiscoveryManager(ztp.db), ztp.jobs)
    ztp.client.app.include_router(nodes_router(SimpleNamespace(ztp_pipeline=pipeline)))
    return ztp.client


def node(client, node_id) -> dict:
    return client.get(f"{NODES}/{node_id}").json()


def provision_job(ztp, node_id, state=JobState.queued, age=timedelta()) -> int:
    with Session(ztp.db.engine) as session:
        job = Job(
            type="acex.ztp.provision",
            subject_type="node",
            subject_id=node_id,
            state=state,
            created_by="alice",
            created_at=datetime.now(UTC) - age,
            started_at=datetime.now(UTC) - age if state == JobState.running else None,
        )
        session.add(job)
        session.commit()
        return job.id


def job_state(ztp, job_id):
    with Session(ztp.db.engine) as session:
        return session.get(Job, job_id).state


def set_previous(ztp, node_id, previous):
    with Session(ztp.db.engine) as session:
        session.get(Node, node_id).ztp_previous_status = previous
        session.commit()


class TestStage:
    def should_await_the_device_until_it_is_discovered(self, ztp, client):
        detail = node(client, ztp.node(ztp.asset(), status=ENROLLED))
        assert (detail["stage"], detail["readiness"], detail["last_seen"]) == ("awaiting_device", "unseen", None)

    def should_await_approval_once_discovered(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=ENROLLED)
        ztp.discover("10.0.0.5")
        assert node(client, node_id)["stage"] == "awaiting_approval"

    def should_be_ready_once_approved(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=ENROLLED)
        discovery = ztp.discover("10.0.0.5")
        ztp.review(discovery["id"], "approve")

        detail = node(client, node_id)

        assert (detail["stage"], detail["approved_ip"]) == ("ready", "10.0.0.5")
        assert [d["id"] for d in detail["discoveries"]] == [discovery["id"]]

    def should_await_the_device_again_after_a_rejection(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=ENROLLED)
        ztp.review(ztp.discover("10.0.0.5")["id"], "reject")
        assert node(client, node_id)["stage"] == "awaiting_device"

    def should_leave_nodes_that_are_not_enrolled_out_of_the_pipeline(self, ztp, client):
        node_id = ztp.node(ztp.asset())
        assert node(client, node_id)["stage"] == "unprovisioned"
        assert client.get(NODES).json()["total"] == 0


class TestStalled:
    def should_flag_provisioning_without_a_job(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=NodeProvisionStatus.provisioning)
        assert node(client, node_id)["stalled"] == "No provisioning job"

    def should_flag_a_job_no_worker_picked_up(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=NodeProvisionStatus.provisioning)
        provision_job(ztp, node_id, age=timedelta(minutes=11))
        assert "not picked up" in node(client, node_id)["stalled"]

    def should_flag_a_job_whose_worker_stopped_reporting(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=NodeProvisionStatus.provisioning)
        provision_job(ztp, node_id, state=JobState.running, age=timedelta(minutes=31))
        assert "without finishing" in node(client, node_id)["stalled"]

    def should_not_flag_a_job_on_its_way(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=NodeProvisionStatus.provisioning)
        provision_job(ztp, node_id, state=JobState.running, age=timedelta(minutes=2))
        assert node(client, node_id)["stalled"] is None

    def should_list_and_count_stalled_nodes_first(self, ztp, client):
        failed = ztp.node(ztp.asset(serial="SN1"), status=NodeProvisionStatus.failed)
        stalled = ztp.node(ztp.asset(serial="SN2"), status=NodeProvisionStatus.provisioning)

        assert [i["node_id"] for i in client.get(NODES).json()["items"]] == [stalled, failed]
        assert [i["node_id"] for i in client.get(NODES, params={"stalled": True}).json()["items"]] == [stalled]
        assert client.get(f"{NODES}/summary").json()["stalled"] == 1


class TestEnroll:
    def should_enroll_and_remember_the_status_before(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=NodeProvisionStatus.provisioned)

        detail = client.post(f"{NODES}/{node_id}/enroll").json()

        assert (detail["provision_status"], detail["ztp_previous_status"], detail["stage"]) == (
            "enrolled",
            "provisioned",
            "awaiting_device",
        )

    def should_refuse_a_node_already_in_ztp(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=ENROLLED)
        assert client.post(f"{NODES}/{node_id}/enroll").status_code == 409


def connections(ztp, node_id) -> list[tuple[str, bool]]:
    with Session(ztp.db.engine) as session:
        rows = session.exec(select(ManagementConnection).where(ManagementConnection.node_id == node_id)).all()
        return sorted((c.target_ip, c.primary) for c in rows)


def add_connection(ztp, node_id, ip, primary=True):
    with Session(ztp.db.engine) as session:
        session.add(ManagementConnection(node_id=node_id, target_ip=ip, primary=primary))
        session.commit()


class TestManagementConnection:
    """The IP an approved device was reached at becomes a management connection of its node."""

    def should_be_learnt_when_a_node_bound_to_the_asset_is_approved(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=ENROLLED)
        ztp.review(ztp.discover("10.0.0.5")["id"], "approve")
        assert connections(ztp, node_id) == [("10.0.0.5", True)]

    def should_be_learnt_when_an_approved_asset_is_claimed(self, ztp, client):
        ztp.review(ztp.discover("10.0.0.5", serial="SN9")["id"], "approve")  # in the pool
        with Session(ztp.db.engine) as session:
            asset_id = session.exec(select(ZtpDiscovery.asset_id)).first()
        node_id = ztp.node(asset_id)

        client.post(f"{NODES}/{node_id}/enroll")

        assert connections(ztp, node_id) == [("10.0.0.5", True)]

    def should_be_added_beside_another_connection(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=ENROLLED)
        add_connection(ztp, node_id, "192.0.2.1")
        ztp.review(ztp.discover("10.0.0.5")["id"], "approve")
        assert connections(ztp, node_id) == [("10.0.0.5", False), ("192.0.2.1", True)]

    def should_not_repeat_a_connection_the_node_has(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=ENROLLED)
        add_connection(ztp, node_id, "10.0.0.5", primary=False)
        ztp.review(ztp.discover("10.0.0.5")["id"], "approve")
        assert connections(ztp, node_id) == [("10.0.0.5", False)]

    def should_wait_for_an_approved_discovery(self, ztp, client):
        node_id = ztp.node(ztp.asset())
        ztp.discover("10.0.0.5")
        client.post(f"{NODES}/{node_id}/enroll")
        assert connections(ztp, node_id) == []


class _Broker:
    """Records what is published, or fails as a broker that is unset or down."""

    def __init__(self, configured=True, error=None):
        self.configured = configured
        self.error = error
        self.published = []

    def publish(self, job_type: str, job_id: int) -> None:
        if self.error:
            raise self.error
        self.published.append((job_type, job_id))


def ready_node(ztp) -> int:
    node_id = ztp.node(ztp.asset(), status=ENROLLED)
    ztp.review(ztp.discover("10.0.0.5")["id"], "approve")
    return node_id


class TestProvision:
    def should_queue_a_job_and_start_provisioning(self, ztp, client):
        node_id = ready_node(ztp)
        ztp.jobs.producer = broker = _Broker()

        detail = client.post(f"{NODES}/{node_id}/provision").json()

        [job] = detail["provision_jobs"]
        assert (detail["provision_status"], detail["stalled"]) == ("provisioning", None)
        assert (job["state"], job["data"], job["created_by"]) == (
            "queued",
            {"node_id": node_id, "method": "cisco_iosxe_python"},
            "alice",
        )
        assert broker.published == [("acex.ztp.provision", job["id"])]

    def should_refuse_a_node_that_is_not_ready(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=ENROLLED)
        ztp.discover("10.0.0.5")
        ztp.jobs.producer = broker = _Broker()

        response = client.post(f"{NODES}/{node_id}/provision")

        assert response.status_code == 409
        assert "awaiting_approval" in response.json()["detail"]
        assert broker.published == []

    def should_refuse_a_node_already_provisioning(self, ztp, client):
        node_id = ready_node(ztp)
        client.post(f"{NODES}/{node_id}/provision")
        assert client.post(f"{NODES}/{node_id}/provision").status_code == 409

    @pytest.mark.parametrize(
        ("broker", "code"), [(_Broker(configured=False), 503), (_Broker(error=ConnectionError("down")), 502)]
    )
    def should_leave_the_node_ready_without_a_broker(self, ztp, client, broker, code):
        node_id = ready_node(ztp)
        ztp.jobs.producer = broker

        assert client.post(f"{NODES}/{node_id}/provision").status_code == code
        detail = node(client, node_id)
        assert (detail["provision_status"], detail["stage"]) == ("enrolled", "ready")


class TestCancel:
    def should_return_to_the_status_before_enrolling(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=NodeProvisionStatus.provisioned)
        client.post(f"{NODES}/{node_id}/enroll")

        detail = client.post(f"{NODES}/{node_id}/cancel").json()

        assert (detail["provision_status"], detail["ztp_previous_status"]) == ("provisioned", None)

    def should_fall_back_to_unprovisioned(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=NodeProvisionStatus.provisioning)
        assert client.post(f"{NODES}/{node_id}/cancel").json()["provision_status"] == "unprovisioned"

    def should_cancel_a_queued_job_and_leave(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=NodeProvisionStatus.provisioning)
        set_previous(ztp, node_id, NodeProvisionStatus.unprovisioned)
        job_id = provision_job(ztp, node_id)

        detail = client.post(f"{NODES}/{node_id}/cancel").json()

        assert detail["provision_status"] == "unprovisioned"
        assert job_state(ztp, job_id) == JobState.cancelled

    def should_leave_a_node_whose_job_was_running_failed(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=NodeProvisionStatus.provisioning)
        job_id = provision_job(ztp, node_id, state=JobState.running)

        assert client.post(f"{NODES}/{node_id}/cancel").json()["provision_status"] == "failed"
        assert job_state(ztp, job_id) == JobState.cancelled
        assert client.post(f"{NODES}/{node_id}/cancel").json()["provision_status"] == "unprovisioned"

    def should_refuse_a_node_not_in_ztp(self, ztp, client):
        node_id = ztp.node(ztp.asset())
        assert client.post(f"{NODES}/{node_id}/cancel").status_code == 409


class TestReset:
    def should_step_back_to_ready(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=NodeProvisionStatus.provisioning)
        ztp.review(ztp.discover("10.0.0.5")["id"], "approve")
        job_id = provision_job(ztp, node_id, state=JobState.running)

        detail = client.post(f"{NODES}/{node_id}/reset").json()

        assert (detail["provision_status"], detail["stage"]) == ("enrolled", "ready")
        assert job_state(ztp, job_id) == JobState.cancelled

    def should_refuse_an_enrolled_node(self, ztp, client):
        node_id = ztp.node(ztp.asset(), status=ENROLLED)
        assert client.post(f"{NODES}/{node_id}/reset").status_code == 409


class TestSummary:
    def should_count_every_node_once_and_the_pool(self, ztp, client):
        ztp.node(ztp.asset(serial="SN1"), status=ENROLLED)
        ztp.node(ztp.asset(serial="SN2"), status=NodeProvisionStatus.provisioned)
        ztp.review(ztp.discover("10.0.0.5", serial="SN9")["id"], "approve")  # approved, bound to no node

        summary = client.get(f"{NODES}/summary").json()

        assert (summary["stages"]["awaiting_device"], summary["stages"]["provisioned"], summary["pool"]) == (1, 1, 1)

    def should_answer_404_for_an_unknown_node(self, client):
        assert client.get(f"{NODES}/999").status_code == 404
        assert client.post(f"{NODES}/999/cancel").status_code == 404
