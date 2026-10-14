"""ZTP methods — `/ztp_methods/*`: what an administrator has chosen for each way a device bootstraps."""

from __future__ import annotations

from acex_devkit.models.ztp import ZtpMethod, ZtpMethodResponse, ZtpMethodUpdate

from acex_client.resources.base import ActionMixin, Resource, action


class ZtpMethods(Resource, ActionMixin):
    """ZTP methods — `/ztp_methods`. One per method; `get()` tells a worker which NED and bootstrap login to use."""

    path = "/ztp_methods"

    @action("GET", "")
    def query(self) -> list[ZtpMethodResponse]: ...

    @action("GET", "{method}")
    def get(self, method: ZtpMethod) -> ZtpMethodResponse: ...

    @action("PUT", "{method}")
    def update(self, method: ZtpMethod, payload: ZtpMethodUpdate) -> ZtpMethodResponse:
        """Change what is chosen for a method; fields left out keep their value.

        An unknown NED raises AcexValidationError.
        """
