from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, IPvAnyAddress

from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.job import JobState


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
    #: A reported fact differs from the claimed asset.
    fact_mismatch = "fact_mismatch"


class ZtpConflict(BaseModel):
    """Something about a discovery an administrator should look at before approving it."""

    kind: ZtpConflictKind
    message: str
    #: The other discovery involved, for the kinds that compare two.
    discovery_id: int | None = None


class ZtpExpected(BaseModel):
    """What the claimed asset says the device should be."""

    asset_id: int
    serial_number: str
    vendor: str | None = None
    hardware_model: str | None = None
    os: str | None = None
    os_version: str | None = None


class ZtpDiscoveryResponse(PersistedResponse, ZtpDiscoverResult):
    """A discovery: the device at `source_ip` says it is `serial_number`."""

    job_id: int | None = None
    source_ip: str
    node_id: int | None = None
    #: Hostname of the matched node's logical node.
    node_hostname: str | None = None
    review_status: ZtpReviewStatus
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    #: The claimed asset of the matched node; None when no node matched.
    expected: ZtpExpected | None = None
    conflicts: list[ZtpConflict] = []


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
