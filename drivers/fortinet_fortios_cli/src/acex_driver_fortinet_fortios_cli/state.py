import re

from acex_devkit.drivers import State
from acex_devkit.models.platform import OS, Vendor
from acex_devkit.models.state import DeviceFacts

from acex_driver_fortinet_fortios_cli.transport.transport import FortiOSTransport


class FortiOSState(State):
    async def get_facts(self, transport: FortiOSTransport) -> DeviceFacts:
        output = (await transport.execute(["get system status"]))[0]
        return DeviceFacts(
            vendor=Vendor.fortinet,
            os=OS.fortinet_fortios,
            os_version=self.find(r"^Version:\s*\S+\s+v(\d+\.\d+\.\d+)", output),
            hardware_model=self.find(r"^Version:\s*(\S+)\s+v\d", output),
            serial_number=self.find(r"^Serial-Number:\s*(\S+)", output),
        )

    @staticmethod
    def find(pattern: str, text: str) -> str | None:
        match = re.search(pattern, text, re.MULTILINE)
        return match.group(1) if match else None
