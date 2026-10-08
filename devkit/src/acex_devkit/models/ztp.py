from enum import StrEnum

from pydantic import BaseModel, IPvAnyAddress


class ZtpMethod(StrEnum):
    """How a device bootstraps itself. One OS can have several methods."""

    #: The device downloads and runs a Python script (Cisco IOS XE guestshell).
    cisco_iosxe_python = "cisco_iosxe_python"


class ZtpDiscoverData(BaseModel):
    """Data of an acex.ztp.discover job: a device that fetched its ZTP bootstrap."""

    #: The address the device fetched its bootstrap from, which discovery logs in to.
    ip: IPvAnyAddress
    #: The bootstrap method it used. Decides how it is discovered.
    method: ZtpMethod
