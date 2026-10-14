"""ZTP review: a discovery only records what a device says it is. Approving it
trusts the device's identity, so the asset with its serial is created or updated
with what was reported; nodes are never touched. What approval would do is
shown first, and approval refuses to write anything other than that."""

from types import SimpleNamespace

import acex.models  # noqa: F401  (every table, for create_all)
import pytest
from acex.api import auth
from acex.api.routers.workers import create_router as workers_router
from acex.api.routers.ztp_discoveries import create_router as discoveries_router
from acex.jobs import JobManager, JobType, JobTypeRegistry
from acex.models import Asset, LogicalNode, Node
from acex.models.node import NodeAdminStatus, NodeProvisionStatus
from acex.models.ztp_method import ZtpMethodRow
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
NED = "cisco_ios_ssh"


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
        with Session(self.db.engine) as session:
            session.add(ZtpMethodRow(method="cisco_iosxe_python", ned=NED))
            session.commit()

    def asset(self, serial: str = SERIAL, **facts) -> int:
        with Session(self.db.engine) as session:
            asset = Asset(serial_number=serial, **(FACTS | facts))
            session.add(asset)
            session.commit()
            return asset.id

    def node(self, asset_id: int, status=NodeProvisionStatus.unprovisioned) -> int:
        with Session(self.db.engine) as session:
            logical = LogicalNode(hostname=f"sw-{asset_id}")
            session.add(logical)
            session.flush()
            node = Node(
                asset_ref_id=asset_id,
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

    def get(self, discovery_id: int) -> dict:
        return self.client.get(f"{DISCOVERIES}/{discovery_id}").json()

    def assets(self, serial: str = SERIAL) -> list[Asset]:
        with Session(self.db.engine) as session:
            return list(session.exec(select(Asset).where(Asset.serial_number == serial)))

    def provision_status(self, node_id: int):
        with Session(self.db.engine) as session:
            return session.get(Node, node_id).provision_status

    def review(self, discovery_id: int, action: str, **body):
        return self.client.post(f"{DISCOVERIES}/{discovery_id}/{action}", json=body or None)

    def approve_many(self, *discoveries, dry_run=False, hashes=True):
        items = [
            {"discovery_id": d["id"], "proposal_hash": d["proposal"]["hash"] if hashes else None} for d in discoveries
        ]
        response = self.client.post(f"{DISCOVERIES}/approve", json={"items": items, "dry_run": dry_run})
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture
def ztp():
    return _Ztp()


class TestDiscovery:
    def should_leave_nodes_alone(self, ztp):
        node_id = ztp.node(ztp.asset())

        discovery = ztp.discover("10.0.0.5")

        assert (discovery["review_status"], discovery["source_ip"], discovery["node_id"]) == (
            "unreviewed",
            "10.0.0.5",
            node_id,
        )
        assert ztp.provision_status(node_id) == NodeProvisionStatus.unprovisioned

    def should_record_one_discovery_per_job(self, ztp):
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


class TestProposal:
    def should_create_an_asset_for_an_unknown_serial(self, ztp):
        proposal = ztp.discover("10.0.0.5")["proposal"]

        assert (proposal["action"], proposal["asset_id"]) == ("create", None)
        assert proposal["asset"] == {"serial_number": SERIAL, **FACTS, "ned_id": NED}

    def should_update_the_facts_that_differ(self, ztp):
        asset_id = ztp.asset(os_version="17.9.4a")

        proposal = ztp.discover("10.0.0.5", hardware_model="C9300-24T")["proposal"]

        assert (proposal["action"], proposal["asset_id"]) == ("update", asset_id)
        assert {c["field"]: (c["current"], c["reported"]) for c in proposal["changes"]} == {
            "hardware_model": ("C9300-48P", "C9300-24T"),
            "os_version": ("17.9.4a", "17.12.3a"),
        }

    def should_change_nothing_on_a_matching_asset(self, ztp):
        ztp.asset()
        proposal = ztp.discover("10.0.0.5", hardware_model="c9300-48p")["proposal"]
        assert (proposal["action"], proposal["changes"]) == ("unchanged", [])

    def should_block_a_vendor_acex_does_not_know(self, ztp):
        proposal = ztp.discover("10.0.0.5", vendor="acme")["proposal"]
        assert proposal["action"] == "blocked"
        assert "acme" in proposal["blocked_by"][0]

    def should_block_a_serial_reported_by_another_vendor(self, ztp):
        ztp.asset(vendor="juniper", os="juniper_junos", os_version=None)
        proposal = ztp.discover("10.0.0.5")["proposal"]
        assert proposal["action"] == "blocked"

    def should_block_a_serial_on_several_assets(self, ztp):
        ztp.asset()
        ztp.asset()
        assert ztp.discover("10.0.0.5")["proposal"]["action"] == "blocked"

    def should_show_no_proposal_once_reviewed(self, ztp):
        discovery = ztp.discover("10.0.0.5")
        ztp.review(discovery["id"], "reject")
        assert ztp.get(discovery["id"])["proposal"] is None


class TestConflicts:
    def should_flag_the_same_serial_from_another_ip(self, ztp):
        first = ztp.discover("10.0.0.5")

        second = ztp.discover("10.0.0.9")

        assert [(c["kind"], c["discovery_id"]) for c in second["conflicts"]] == [("serial_on_other_ip", first["id"])]

    def should_flag_an_ip_that_reported_another_serial(self, ztp):
        ztp.discover("10.0.0.5", serial="OTHER123")

        discovery = ztp.discover("10.0.0.5")

        assert [c["kind"] for c in discovery["conflicts"]] == ["ip_with_other_serial"]

    def should_flag_the_serial_of_a_provisioned_node(self, ztp):
        node_id = ztp.node(ztp.asset(), status=NodeProvisionStatus.provisioned)

        [conflict] = ztp.discover("10.0.0.5")["conflicts"]

        assert (conflict["kind"], conflict["node_id"]) == ("serial_of_provisioned_node", node_id)

    def should_ignore_rejected_discoveries(self, ztp):
        first = ztp.discover("10.0.0.5")
        ztp.review(first["id"], "reject")

        assert ztp.discover("10.0.0.9")["conflicts"] == []


class TestApprove:
    def should_create_the_asset(self, ztp):
        discovery = ztp.discover("10.0.0.5")

        approved = ztp.review(discovery["id"], "approve", proposal_hash=discovery["proposal"]["hash"]).json()

        [asset] = ztp.assets()
        assert (approved["review_status"], approved["reviewed_by"], approved["asset_id"]) == (
            "approved",
            "alice",
            asset.id,
        )
        assert (asset.hardware_model, asset.os_version, asset.ned_id) == ("C9300-48P", "17.12.3a", NED)

    def should_update_the_asset_and_leave_its_node_alone(self, ztp):
        asset_id = ztp.asset(os_version="17.9.4a")
        node_id = ztp.node(asset_id, status=NodeProvisionStatus.provisioned)
        discovery = ztp.discover("10.0.0.5")

        ztp.review(discovery["id"], "approve")

        [asset] = ztp.assets()
        assert asset.os_version == "17.12.3a"
        assert ztp.provision_status(node_id) == NodeProvisionStatus.provisioned

    def should_refuse_a_proposal_that_changed_since_it_was_shown(self, ztp):
        discovery = ztp.discover("10.0.0.5")
        ztp.asset(hardware_model="C9300-24T")  # created behind the reviewer's back

        response = ztp.review(discovery["id"], "approve", proposal_hash=discovery["proposal"]["hash"])

        assert response.status_code == 409
        assert ztp.get(discovery["id"])["review_status"] == "unreviewed"

    def should_refuse_a_blocked_proposal(self, ztp):
        discovery = ztp.discover("10.0.0.5", vendor="acme")
        assert ztp.review(discovery["id"], "approve").status_code == 409
        assert ztp.assets() == []

    def should_approve_despite_an_identity_conflict_on_its_own(self, ztp):
        ztp.discover("10.0.0.5")
        second = ztp.discover("10.0.0.9")
        assert ztp.review(second["id"], "approve").status_code == 200

    def should_reject_the_other_reports_of_the_serial(self, ztp):
        first = ztp.discover("10.0.0.5")
        second = ztp.discover("10.0.0.9")

        ztp.review(second["id"], "approve")

        assert ztp.get(first["id"])["review_status"] == "rejected"

    def should_refuse_to_review_twice(self, ztp):
        discovery = ztp.discover("10.0.0.5")
        ztp.review(discovery["id"], "approve")

        assert ztp.review(discovery["id"], "approve").status_code == 409
        assert ztp.review(discovery["id"], "reject").status_code == 409

    def should_answer_404_for_an_unknown_discovery(self, ztp):
        assert ztp.review(999, "approve").status_code == 404
        assert ztp.client.get(f"{DISCOVERIES}/999").status_code == 404


class TestBulk:
    def should_write_nothing_on_a_dry_run(self, ztp):
        discoveries = [ztp.discover(f"10.0.0.{i}", serial=f"SN{i}") for i in range(3)]

        result = ztp.approve_many(*discoveries, dry_run=True)

        assert [r["outcome"] for r in result["results"]] == ["would_approve"] * 3
        assert result["summary"] == {"would_approve": 3, "create": 3}
        assert all(ztp.get(d["id"])["review_status"] == "unreviewed" for d in discoveries)
        assert all(ztp.assets(f"SN{i}") == [] for i in range(3))

    def should_do_what_the_dry_run_said(self, ztp):
        ztp.asset(serial="SN1", os_version="17.9.4a")
        discoveries = [ztp.discover(f"10.0.0.{i}", serial=f"SN{i}") for i in range(3)]
        dry = ztp.approve_many(*discoveries, dry_run=True)

        real = ztp.approve_many(*discoveries)

        assert [r["proposal"] for r in real["results"]] == [r["proposal"] for r in dry["results"]]
        assert real["summary"] == {"approved": 3, "create": 2, "update": 1}

    def should_skip_an_identity_conflict(self, ztp):
        ztp.discover("10.0.0.5", serial="SN1")
        conflicted = ztp.discover("10.0.0.5", serial="SN2")
        clean = ztp.discover("10.0.0.6", serial="SN3")

        result = ztp.approve_many(conflicted, clean)

        assert [r["outcome"] for r in result["results"]] == ["skipped", "approved"]
        assert "on its own" in result["results"][0]["reason"]

    def should_skip_a_proposal_that_changed(self, ztp):
        discovery = ztp.discover("10.0.0.5")
        ztp.asset(hardware_model="C9300-24T")

        [result] = ztp.approve_many(discovery)["results"]

        assert result["outcome"] == "skipped"
        assert result["proposal"]["action"] == "update"

    def should_reject_many(self, ztp):
        discoveries = [ztp.discover(f"10.0.0.{i}", serial=f"SN{i}") for i in range(2)]

        response = ztp.client.post(f"{DISCOVERIES}/reject", json={"discovery_ids": [d["id"] for d in discoveries]})

        assert response.json()["summary"] == {"rejected": 2}


class TestAccess:
    def should_keep_reviews_out_of_the_public_ztp_prefix(self):
        # Everything under /api/v1/ztp is served without a token, for devices.
        for path in (DISCOVERIES, f"{DISCOVERIES}/1/approve", f"{DISCOVERIES}/approve"):
            assert not any(path == p or path.startswith(f"{p}/") for p in auth._PUBLIC_PATH_PREFIXES)
