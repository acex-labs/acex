"""Minimal example NED against an in-memory fake device. Run: python -m acex_devkit.drivers.example_ned"""

import re

from acex_devkit.configdiffer import Diff
from acex_devkit.drivers import Actions, Codec, NetworkElementDriver, State, Transport
from acex_devkit.models.actions import PingParams, PingResult
from acex_devkit.models.codec_result import ParseResult, RenderResult
from acex_devkit.models.composed_configuration import ComposedConfiguration, System, SystemConfig
from acex_devkit.models.ned import Platform
from acex_devkit.models.node_response import NodeInstance
from acex_devkit.models.platform import OS, Vendor
from acex_devkit.models.state import ArpEntry


class FakeCliTransport(Transport[str]):
    """Pretends to be an SSH session to a CLI device."""

    async def open(self) -> None:
        login = self.credential("userpass")
        enable = self.credential("privilege_escalation", required=False)
        print(f"[transport] open {self.address} as {login.fields['username']} (enable: {bool(enable)})")
        self.running = "hostname old-name\nenable secret s3cr3t\n"

    async def close(self) -> None:
        print("[transport] close")

    async def get_config(self) -> str:
        return self.running

    async def apply(self, payload: str) -> str:
        commands = [line for line in payload.splitlines() if line.strip()]
        print(f"[transport] configure: {commands}")
        self.running = "\n".join([*commands, *self.running.splitlines()[1:]]) + "\n"
        return "ok"

    async def execute(self, request: list[str]) -> list[str]:
        outputs = {
            "show running-config": self.running,
            "show ip arp": "10.0.0.1  aabb.cc00.0100  Gi1\n10.0.0.2  aabb.cc00.0200  Gi2\n",
            "ping 10.0.0.1 repeat 5": "Success rate is 100 percent (5/5)",
        }
        return [outputs.get(command, f"% Invalid input: {command}") for command in request]


class ExampleCodec(Codec[str]):
    """Handles hostname only."""

    def render(self, config: ComposedConfiguration, node: NodeInstance) -> RenderResult[str]:
        return RenderResult(payload=f"hostname {config.system.config.hostname.value}\n")

    def parse(self, raw: str, node: NodeInstance) -> ParseResult:
        match = re.search(r"^hostname (\S+)", raw, re.MULTILINE)
        hostname = match.group(1) if match else None
        return ParseResult(configuration=ComposedConfiguration(system=System(config=SystemConfig(hostname=hostname))))

    def render_patch(self, diff: Diff, node: NodeInstance) -> str:
        return "".join(
            f"hostname {component.after.hostname.value}\n"
            for component in [*diff.added, *diff.changed]
            if component.path == ["system", "config"] and component.after.hostname is not None
        )

    def mask(self, raw: str) -> str:
        return re.sub(r"(secret|password) (?!<REDACTED>)\S+", r"\1 <REDACTED>", raw)


class ExampleState(State):
    async def get_arp_table(self, transport: Transport) -> list[ArpEntry]:
        output = (await transport.execute(["show ip arp"]))[0]
        return [
            ArpEntry(ip_address=ip, mac_address=mac, interface=interface)
            for ip, mac, interface in (line.split() for line in output.splitlines())
        ]


class ExampleActions(Actions):
    async def ping(self, transport: Transport, params: PingParams) -> PingResult:
        output = (await transport.execute([f"ping {params.target} repeat {params.count}"]))[0]
        received, sent = re.search(r"\((\d+)/(\d+)\)", output).groups()
        return PingResult(sent=int(sent), received=int(received))


class ExampleDriver(NetworkElementDriver):
    """Example NED against a fake CLI device."""

    codec_class = ExampleCodec
    transport_class = FakeCliTransport
    state_class = ExampleState
    actions_class = ExampleActions

    platforms = [Platform(vendor=Vendor.cisco, os=OS.cisco_ios)]


# Example worker:
if __name__ == "__main__":
    print("test")

    from acex_client import Acex

    acex = Acex(base_url="http://localhost:8080")

    node = acex.inventory.node_instances.get(29)

    def get_userpass(node, credential_type: str):
        for cred in node.credentials:
            if cred.credential_type == credential_type:
                return cred

    creds = get_userpass(node, "userpass")
    driver = acex.neds.load(node.asset.ned_id)

    # ned = ExampleDriver()

    # session = ned.session(node, )
