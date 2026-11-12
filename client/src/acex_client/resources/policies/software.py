"""Software policy — `/policies/software/*`: the versions approved per vendor or hardware model."""

from __future__ import annotations

from acex_devkit.models.platform import OS, Vendor
from acex_devkit.models.policy import (
    SoftwarePolicyCreate,
    SoftwarePolicyResponse,
    SoftwarePolicyUpdate,
    SoftwareVersionInUse,
)

from acex_client.resources.base import ActionMixin, Resource, action


class SoftwarePolicies(Resource, ActionMixin):
    """Software policy — `/policies/software`. One entry per approved version; at most one golden per vendor,
    hardware model and OS. A version not approved is not allowed."""

    path = "/policies/software"

    @action("GET", "")
    def query(self) -> list[SoftwarePolicyResponse]: ...

    @action("GET", "versions")
    def versions(self, vendor: Vendor, os: OS, hardware_model: str | None = None) -> list[SoftwareVersionInUse]:
        """The versions assets in the inventory report, newest first; without a model, every model of the vendor."""

    @action("GET", "{id}")
    def get(self, id: int) -> SoftwarePolicyResponse: ...

    @action("POST", "")
    def create(self, payload: SoftwarePolicyCreate) -> SoftwarePolicyResponse:
        """A version already approved, or a second golden one, raises AcexConflictError."""

    @action("PATCH", "{id}")
    def update(self, id: int, payload: SoftwarePolicyUpdate) -> SoftwarePolicyResponse:
        """Change the fields sent; golden False makes it accepted, hardware_model None the vendor's."""

    @action("DELETE", "{id}")
    def delete(self, id: int) -> None: ...
