from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, IPvAnyAddress

from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.job import JobResponse, JobState


class ZtpMethod(StrEnum):
    """How a device bootstraps itself. One OS can have several methods."""

    #: The device downloads and runs a Python script (Cisco IOS XE guestshell).
    cisco_iosxe_python = "cisco_iosxe_python"


class ZtpMethodInfo(BaseModel):
    """How a ZTP method is presented to an administrator."""

    label: str
    description: str


#: One entry per ZtpMethod; add one with every new method.
ZTP_METHOD_INFO: dict[ZtpMethod, ZtpMethodInfo] = {
    ZtpMethod.cisco_iosxe_python: ZtpMethodInfo(
        label="Cisco IOS XE — Python",
        description="The device downloads ztp.py over HTTP and runs it in guestshell.",
    ),
}


class ZtpMethodResponse(ZtpMethodInfo):
    """A ZTP method, and what an administrator has chosen for it."""

    method: ZtpMethod
    #: The NED discovery uses for devices that bootstrap this way. None until one is chosen.
    ned: str | None = None
    #: The temporary login the bootstrap gives a device and discovery logs in with,
    #: until onboarding rotates it. Not a secret: the bootstrap is public.
    bootstrap_username: str | None = None
    bootstrap_password: str | None = None
    updated_by: str | None = None
    updated_at: datetime | None = None


class ZtpMethodUpdate(BaseModel):
    """Change what is chosen for a ZTP method. Only the fields sent change; None clears one."""

    ned: str | None = None
    bootstrap_username: str | None = None
    bootstrap_password: str | None = None


class ZtpDiscoverData(BaseModel):
    """Data of an acex.ztp.discover job: a device that fetched its ZTP bootstrap."""

    #: The address the device fetched its bootstrap from, which discovery logs in to.
    ip: IPvAnyAddress
    #: The bootstrap method it used. Decides how it is discovered.
    method: ZtpMethod


class ZtpDiscoverResult(BaseModel):
    """Result of an acex.ztp.discover job: what the device says it is.

    Self-reported and unverified, so plain strings: a value ACEX has no enum
    member for is still worth showing to the administrator who reviews it.
    """

    serial_number: str
    vendor: str | None = None
    hardware_model: str | None = None
    os: str | None = None
    os_version: str | None = None


class ZtpReviewStatus(StrEnum):
    """Where a discovery stands with the administrator who has to approve it."""

    unreviewed = "unreviewed"
    approved = "approved"
    rejected = "rejected"


class ZtpConflictKind(StrEnum):
    #: The same serial number was reported from another IP.
    serial_on_other_ip = "serial_on_other_ip"
    #: The same IP has reported another serial number.
    ip_with_other_serial = "ip_with_other_serial"
    #: The serial belongs to a provisioned node: the device may have been reset.
    serial_of_provisioned_node = "serial_of_provisioned_node"


#: Conflicts that put the device's identity in doubt. A bulk approval skips a
#: discovery with one; it can still be approved on its own.
IDENTITY_CONFLICTS = frozenset({ZtpConflictKind.serial_on_other_ip, ZtpConflictKind.ip_with_other_serial})


class ZtpConflict(BaseModel):
    """Something about a discovery an administrator should look at before approving it."""

    kind: ZtpConflictKind
    message: str
    #: The other discovery involved, for the kinds that compare two.
    discovery_id: int | None = None
    #: The node involved, for serial_of_provisioned_node.
    node_id: int | None = None


class ZtpApprovalAction(StrEnum):
    """What approving a discovery does to the asset with its serial number."""

    #: No asset has the serial; one is created from the reported facts.
    create = "create"
    #: The asset exists; the reported facts that differ are written to it.
    update = "update"
    #: The asset exists and already matches.
    unchanged = "unchanged"
    #: The discovery cannot be approved; `blocked_by` says why.
    blocked = "blocked"


class ZtpFactChange(BaseModel):
    field: str
    current: str | None = None
    reported: str | None = None


class ZtpProposedAsset(BaseModel):
    """The asset as it will be once the discovery is approved."""

    serial_number: str
    vendor: str | None = None
    hardware_model: str | None = None
    os: str | None = None
    os_version: str | None = None
    ned_id: str | None = None


class ZtpApprovalProposal(BaseModel):
    """What approving the discovery would do, computed by the same code that approves it."""

    action: ZtpApprovalAction
    #: The existing asset; None for create and for some blocked proposals.
    asset_id: int | None = None
    asset: ZtpProposedAsset | None = None
    #: For update: the facts that will be written.
    changes: list[ZtpFactChange] = []
    blocked_by: list[str] = []
    #: Identifies this exact proposal. Sent back on approve, so nothing is
    #: written that differs from what the administrator saw.
    hash: str


class ZtpDiscoveryResponse(PersistedResponse, ZtpDiscoverResult):
    """A discovery: the device at `source_ip` says it is `serial_number`."""

    job_id: int | None = None
    source_ip: str
    #: The asset the discovery was approved as; None until approved.
    asset_id: int | None = None
    #: The node the asset with this serial is bound to, if any. Approval never changes it.
    node_id: int | None = None
    #: Hostname of that node's logical node.
    node_hostname: str | None = None
    review_status: ZtpReviewStatus
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    conflicts: list[ZtpConflict] = []
    #: What approving would do; None once reviewed.
    proposal: ZtpApprovalProposal | None = None


class ZtpApproveRequest(BaseModel):
    #: The hash of the proposal the administrator saw. Approval is refused if it
    #: no longer matches. Leave out to approve whatever the proposal now is.
    proposal_hash: str | None = None


class ZtpBulkApproveItem(BaseModel):
    discovery_id: int
    proposal_hash: str | None = None


class ZtpBulkApprove(BaseModel):
    items: list[ZtpBulkApproveItem]
    #: Work out what would happen without writing anything.
    dry_run: bool = False


class ZtpBulkReject(BaseModel):
    discovery_ids: list[int]


class ZtpBulkOutcome(StrEnum):
    approved = "approved"
    #: A dry run would approve it.
    would_approve = "would_approve"
    rejected = "rejected"
    skipped = "skipped"


class ZtpBulkItemResult(BaseModel):
    discovery_id: int
    outcome: ZtpBulkOutcome
    #: Why it was skipped.
    reason: str | None = None
    proposal: ZtpApprovalProposal | None = None


class ZtpBulkResult(BaseModel):
    results: list[ZtpBulkItemResult]
    #: Counts per proposal action (approve) and per outcome.
    summary: dict[str, int]


class ZtpCallStage(StrEnum):
    """Where a device that called in stands before anyone reviews it, from its latest discovery job."""

    #: Fetched its bootstrap; no worker has picked up the discovery yet.
    waiting = "waiting"
    #: A worker is logging in to it.
    discovering = "discovering"
    #: The worker could not find out what it is.
    failed = "failed"
    #: It said what it is; the discovery waits in review.
    reported = "reported"


class ZtpCallAttempt(BaseModel):
    """One bootstrap fetch and the discovery job it started."""

    job_id: int
    state: JobState
    attempts: int
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    #: Set once the worker reported what the device is.
    discovery_id: int | None = None
    serial_number: str | None = None
    review_status: ZtpReviewStatus | None = None


class ZtpCall(BaseModel):
    """A device that called in, by the IP it fetched its bootstrap from.

    A device that reboots calls in again, so one IP gathers several attempts.
    """

    source_ip: str
    method: ZtpMethod
    stage: ZtpCallStage
    #: When it last fetched its bootstrap.
    last_seen: datetime
    #: Newest first.
    attempts: list[ZtpCallAttempt]


class ZtpAssetReadiness(StrEnum):
    """How far a node's device has come before provisioning, from the discoveries of its serial."""

    #: No discovery of the serial, or only rejected ones.
    unseen = "unseen"
    #: The latest discovery waits for an administrator.
    awaiting_review = "awaiting_review"
    #: The latest discovery is approved: identity and address are trusted.
    ready = "ready"


class ZtpStage(StrEnum):
    """Where a node stands in ZTP.

    Before provisioning starts this comes from the asset's readiness; from then
    on it is the node's provision_status.
    """

    awaiting_device = "awaiting_device"
    awaiting_approval = "awaiting_approval"
    ready = "ready"
    provisioning = "provisioning"
    provisioned = "provisioned"
    failed = "failed"
    adopted = "adopted"
    unprovisioned = "unprovisioned"


#: The stages a node is in the pipeline for.
PIPELINE_STAGES = (
    ZtpStage.awaiting_device,
    ZtpStage.awaiting_approval,
    ZtpStage.ready,
    ZtpStage.provisioning,
    ZtpStage.failed,
)


class ZtpNodeAsset(BaseModel):
    id: int
    serial_number: str
    vendor: str | None = None
    hardware_model: str | None = None
    os: str | None = None
    os_version: str | None = None
    ned_id: str | None = None


class ZtpPipelineNode(BaseModel):
    """A node and where it stands in ZTP."""

    node_id: int
    hostname: str | None = None
    site: str | None = None
    admin_status: str
    provision_status: str
    #: The status the node had when it was enrolled; cancelling ZTP returns it there.
    ztp_previous_status: str | None = None
    stage: ZtpStage
    #: Why a provisioning node is not getting anywhere: no job, or a job lost on its queue or its worker.
    stalled: str | None = None
    #: None when the node is bound to an asset cluster.
    asset: ZtpNodeAsset | None = None
    readiness: ZtpAssetReadiness | None = None
    #: When the device was last discovered.
    last_seen: datetime | None = None
    #: The address of the approved discovery, which provisioning uses.
    approved_ip: str | None = None


class ZtpNodeDetail(ZtpPipelineNode):
    #: Discoveries of the asset's serial, newest first.
    discoveries: list[ZtpDiscoveryResponse] = []
    #: Provisioning jobs of the node, newest first.
    provision_jobs: list[JobResponse] = []


class ZtpPipelineSummary(BaseModel):
    #: Nodes per stage, every node counted once.
    stages: dict[ZtpStage, int]
    #: Approved assets not bound to any node: ready for a node to be assigned.
    pool: int
    #: Provisioning nodes that are not getting anywhere.
    stalled: int = 0
