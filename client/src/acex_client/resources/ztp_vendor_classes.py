"""ZTP vendor classes — `/ztp_vendor_classes/*`: DHCP vendor classes and the ZTP method each maps to."""

from __future__ import annotations

from acex_devkit.models.ztp import ZtpVendorClassCreate, ZtpVendorClassResponse, ZtpVendorClassUpdate

from acex_client.resources.base import ActionMixin, Resource, action


class ZtpVendorClasses(Resource, ActionMixin):
    """ZTP vendor classes — `/ztp_vendor_classes`. A vendor class maps to one method, or none until configured."""

    path = "/ztp_vendor_classes"

    @action("GET", "")
    def query(self) -> list[ZtpVendorClassResponse]: ...

    @action("POST", "")
    def create(self, payload: ZtpVendorClassCreate) -> ZtpVendorClassResponse:
        """An existing vendor class raises AcexConflictError."""

    @action("PATCH", "{id}")
    def update(self, id: int, payload: ZtpVendorClassUpdate) -> ZtpVendorClassResponse:
        """Change the fields sent; method None unmaps the vendor class."""

    @action("DELETE", "{id}")
    def delete(self, id: int) -> None: ...
