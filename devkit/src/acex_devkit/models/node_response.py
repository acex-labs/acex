from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from acex_devkit.models.asset import (
    AssetClusterResponse,
    AssetResponse,
)
from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.logical_node import LogicalNodeResponse
from acex_devkit.models.management_connection import ManagementConnectionResponse


class AssetRefType(StrEnum):
    asset = "asset"
    asset_cluster = "asset_cluster"


class NodeAdminStatus(StrEnum):
    """Operator intent for the node."""

    planned = "planned"
    active = "active"
    decommissioned = "decommissioned"


class NodeProvisionStatus(StrEnum):
    """Where the node's device is in the provisioning lifecycle. Set by the provisioning flow, not by operators.

    With no provisioning under way the node sits in a steady state (unprovisioned, adopted,
    provisioned); during ZTP it shows the current stage, named after who is being waited on.
    Init and discovery happen before ACEX knows which node a device is, so they are tracked
    on the job, not here.
    """

    unprovisioned = "unprovisioned"  # steady: no provisioning requested, never provisioned by ACEX
    adopted = "adopted"  # steady: brownfield, already running when brought under management
    awaiting_device = "awaiting_device"  # claimed; waiting for the device to be discovered
    awaiting_approval = "awaiting_approval"  # a discovery matched this node; waiting for an administrator
    provisioning = "provisioning"  # approved; full config being pushed and verified
    provisioned = "provisioned"  # steady: provisioned by ACEX and verified
    failed = "failed"  # stuck until retried or cancelled; the reason is on the job


class NodeBase(BaseModel):
    asset_ref_id: int
    asset_ref_type: AssetRefType | None = None
    logical_node_id: int
    admin_status: NodeAdminStatus | None = None
    provision_status: NodeProvisionStatus | None = None


class NodeListItem(PersistedResponse, NodeBase):
    hostname: str | None = None
    site: str | None = None
    role: str | None = None
    regions: list[str] = []
    vendor: str | None = None
    os: str | None = None
    ned_id: str | None = None
    management_connections: list[ManagementConnectionResponse] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NodeCreate(NodeBase):
    pass


class NodeUpdate(BaseModel):
    asset_ref_id: int | None = None
    asset_ref_type: AssetRefType | None = None
    logical_node_id: int | None = None
    admin_status: NodeAdminStatus | None = None
    provision_status: NodeProvisionStatus | None = None


class NodeResponse(PersistedResponse, NodeBase):
    asset: Annotated[AssetResponse | AssetClusterResponse, Field(discriminator="type")]
    logical_node: LogicalNodeResponse
    regions: list[str] = []
    created_at: datetime
    updated_at: datetime | None = None


__all__ = [
    "LogicalNodeResponse",
    "AssetRefType",
    "NodeAdminStatus",
    "NodeProvisionStatus",
    "NodeBase",
    "NodeListItem",
    "NodeResponse",
]
