"""ZTP review: a discovery only records what a device says it is. It is matched
to the node awaiting that serial number, and nothing is trusted until an
administrator approves it; a rejection sends the node back to waiting."""

from types import SimpleNamespace

import acex.models  # noqa: F401  (every table, for create_all)
import pytest
from acex.api import auth
from acex.api.routers.workers import create_router as workers_router
from acex.api.routers.ztp_discoveries import create_router as discoveries_router
from acex.jobs import JobManager, JobType, JobTypeRegistry
from acex.models import Asset, LogicalNode, ManagementConnection, Node
from acex.models.node import NodeAdminStatus, NodeProvisionStatus
from acex.settings import RabbitMQSettings
from acex.ztp import ZtpDiscoveryManager
from acex_devkit.models.job import JobUpdate
from acex_devkit.models.ztp import ZtpDiscoverData, ZtpDiscoverResult
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

DISCOVERIES = "/api/v1/ztp_discoveries"
SERIAL = "FCW2233L0AB"
FACTS = {"vendor": "cisco", "hardware_model": "C9300-48P", "os": "cisco_iosxe", "os_version": "17.12.3a"}


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


class _Producer:
    configured = True

    def publish(self, job_type: str, job_id: int) -> None:
        pass


class _Ztp:
    """The workers and discoveries routers on a fresh database."""

    def __init__(self):
        self.db = _Db()
        self.jobs = JobManager(self.db, _Producer())
        self.caller = {"azp": "worker-a", "preferred_username": "alice"}
        engine = SimpleNamespace(
            jobs=self.jobs,
            settings=SimpleNamespace(rabbitmq=RabbitMQSettings()),
            ztp_discoveries=ZtpDiscoveryManager(self.db),
        )
        app = FastAPI()
        app.include_router(workers_router(engine))
        app.include_router(discoveries_router(engine))
        app.dependency_overrides[auth.get_current_user] = lambda: self.caller
        self.client = TestClient(app)

    def claimed_node(self, serial: str = SERIAL, status=NodeProvisionStatus.awaiting_device) -> int:
        with Session(self.db.engine) as session:
            asset = Asset(serial_number=serial, **FACTS)
            logical = LogicalNode(hostname=f"sw-{serial}")
            session.add_all([asset, logical])
            session.flush()
            node = Node(
                asset_ref_id=asset.id,
                logical_node_id=logical.id,
                admin_status=NodeAdminStatus.planned,
                provision_status=status,
            )
            session.add(node)
            session.commit()
            return node.id

    def discover(self, ip: str, serial: str = SERIAL, **facts) -> dict:
        """A device at `ip` fetches its bootstrap and a worker reports what it found."""
        job = self.jobs.enqueue("acex.ztp.discover", {"ip": ip, "method": "cisco_iosxe_python"}, created_by="system")
        self.client.patch(f"/api/v1/workers/jobs/{job.id}", json={"state": "running"})
        response = self.client.patch(
            f"/api/v1/workers/jobs/{job.id}",
            json={"state": "succeeded", "result": {"serial_number": serial, **(FACTS | facts)}},
        )
        assert response.status_code == 200, response.text
        [discovery] = self.client.get(DISCOVERIES, params={"source_ip": ip, "serial_number": serial}).json()["items"]
        return discovery

    def node(self, node_id: int) -> Node:
        with Session(self.db.engine) as session:
            return session.get(Node, node_id)

    def connections(self, node_id: int) -> list[ManagementConnection]:
        with Session(self.db.engine) as session:
            return list(session.exec(select(ManagementConnection).where(ManagementConnection.node_id == node_id)))

    def review(self, discovery_id: int, action: str):
        return self.client.post(f"{DISCOVERIES}/{discovery_id}/{action}")


@pytest.fixture
def ztp():
    return _Ztp()


class TestDiscovery:
    def should_match_the_node_awaiting_the_serial(self, ztp):
        node_id = ztp.claimed_node()

        discovery = ztp.discover("10.0.0.5")

        assert (discovery["node_id"], discovery["review_status"], discovery["source_ip"]) == (
            node_id,
            "unreviewed",
            "10.0.0.5",
        )
        assert discovery["expected"]["serial_number"] == SERIAL
        assert discovery["node_hostname"] == f"sw-{SERIAL}"
        assert discovery["conflicts"] == []
        assert ztp.node(node_id).provision_status == NodeProvisionStatus.awaiting_approval

    def should_trust_nothing_before_approval(self, ztp):
        node_id = ztp.claimed_node()
        ztp.discover("10.0.0.5")
        assert ztp.connections(node_id) == []

    def should_record_a_device_no_node_awaits(self, ztp):
        ztp.claimed_node(status=NodeProvisionStatus.adopted)

        discovery = ztp.discover("10.0.0.5")

        assert (discovery["node_id"], discovery["expected"]) == (None, None)

    def should_record_one_discovery_per_job(self, ztp):
        ztp.claimed_node()
        ztp.discover("10.0.0.5")
        [job] = ztp.client.get("/api/v1/workers/jobs").json()["items"]

        resent = ztp.client.patch(
            f"/api/v1/workers/jobs/{job['id']}", json={"state": "succeeded", "result": {"serial_number": SERIAL}}
        )

        assert resent.status_code == 200
        assert ztp.client.get(DISCOVERIES).json()["total"] == 1

    def should_leave_the_job_running_if_the_discovery_cannot_be_stored(self, ztp):
        def broken(session, job, result):
            raise RuntimeError("database gone")

        job_types = JobTypeRegistry()
        job_types.register(
            JobType("acex.ztp.discover", data=ZtpDiscoverData, result=ZtpDiscoverResult, on_succeeded=broken)
        )
        jobs = JobManager(ztp.db, _Producer(), job_types)
        job = jobs.enqueue("acex.ztp.discover", {"ip": "10.0.0.5", "method": "cisco_iosxe_python"}, created_by="x")
        jobs.update(job.id, JobUpdate(state="running"), worker="worker-a")

        with pytest.raises(RuntimeError):
            jobs.update(job.id, JobUpdate(state="succeeded", result={"serial_number": SERIAL}), worker="worker-a")

        assert jobs.get(job.id).state == "running"


class TestConflicts:
    def should_flag_the_same_serial_from_another_ip(self, ztp):
        ztp.claimed_node()
        first = ztp.discover("10.0.0.5")

        second = ztp.discover("10.0.0.9")

        assert [(c["kind"], c["discovery_id"]) for c in second["conflicts"]] == [("serial_on_other_ip", first["id"])]

    def should_flag_an_ip_that_reported_another_serial(self, ztp):
        ztp.discover("10.0.0.5", serial="OTHER123")

        discovery = ztp.discover("10.0.0.5")

        assert [c["kind"] for c in discovery["conflicts"]] == ["ip_with_other_serial"]

    def should_flag_facts_that_differ_from_the_asset(self, ztp):
        ztp.claimed_node()

        discovery = ztp.discover("10.0.0.5", hardware_model="C9200L-24T")

        [conflict] = discovery["conflicts"]
        assert conflict["kind"] == "fact_mismatch"
        assert "hardware_model" in conflict["message"]

    def should_ignore_rejected_discoveries(self, ztp):
        ztp.claimed_node()
        first = ztp.discover("10.0.0.5")
        ztp.review(first["id"], "reject")

        assert ztp.discover("10.0.0.9")["conflicts"] == []


class TestApprove:
    def should_provision_the_node_at_the_reported_ip(self, ztp):
        node_id = ztp.claimed_node()
        discovery = ztp.discover("10.0.0.5")

        approved = ztp.review(discovery["id"], "approve").json()

        assert (approved["review_status"], approved["reviewed_by"]) == ("approved", "alice")
        assert ztp.node(node_id).provision_status == NodeProvisionStatus.provisioning
        [connection] = ztp.connections(node_id)
        assert (connection.target_ip, connection.primary) == ("10.0.0.5", True)

    def should_reject_the_other_reports_for_the_node(self, ztp):
        ztp.claimed_node()
        first = ztp.discover("10.0.0.5")
        second = ztp.discover("10.0.0.9")

        ztp.review(second["id"], "approve")

        assert ztp.client.get(f"{DISCOVERIES}/{first['id']}").json()["review_status"] == "rejected"

    def should_refuse_a_discovery_without_a_node(self, ztp):
        discovery = ztp.discover("10.0.0.5")
        assert ztp.review(discovery["id"], "approve").status_code == 409

    def should_refuse_to_review_twice(self, ztp):
        ztp.claimed_node()
        discovery = ztp.discover("10.0.0.5")
        ztp.review(discovery["id"], "approve")

        assert ztp.review(discovery["id"], "approve").status_code == 409
        assert ztp.review(discovery["id"], "reject").status_code == 409

    def should_answer_404_for_an_unknown_discovery(self, ztp):
        assert ztp.review(999, "approve").status_code == 404
        assert ztp.client.get(f"{DISCOVERIES}/999").status_code == 404


class TestReject:
    def should_send_the_node_back_to_waiting_for_its_device(self, ztp):
        node_id = ztp.claimed_node()
        discovery = ztp.discover("10.0.0.5")

        rejected = ztp.review(discovery["id"], "reject").json()

        assert rejected["review_status"] == "rejected"
        assert ztp.node(node_id).provision_status == NodeProvisionStatus.awaiting_device
        assert ztp.connections(node_id) == []

    def should_keep_the_node_waiting_for_review_while_another_report_is_open(self, ztp):
        node_id = ztp.claimed_node()
        first = ztp.discover("10.0.0.5")
        ztp.discover("10.0.0.9")

        ztp.review(first["id"], "reject")

        assert ztp.node(node_id).provision_status == NodeProvisionStatus.awaiting_approval


class TestAccess:
    def should_keep_reviews_out_of_the_public_ztp_prefix(self):
        # Everything under /api/v1/ztp is served without a token, for devices.
        for path in (DISCOVERIES, f"{DISCOVERIES}/1/approve"):
            assert not any(path == p or path.startswith(f"{p}/") for p in auth._PUBLIC_PATH_PREFIXES)
