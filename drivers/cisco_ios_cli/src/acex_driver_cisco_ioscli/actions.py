import re

from acex_devkit.drivers import Actions
from acex_devkit.exceptions import DriverException
from acex_devkit.models.actions import PingParams, PingResult

from acex_driver_cisco_ioscli.transport.transport import CiscoIOSTransport


class CiscoIOSActions(Actions):
    SUMMARY = re.compile(
        r"Success rate is \d+ percent \((?P<received>\d+)/(?P<sent>\d+)\)"
        r"(?:, round-trip min/avg/max = (?P<min>\d+)/(?P<avg>\d+)/(?P<max>\d+) ms)?"
    )

    async def ping(self, transport: CiscoIOSTransport, params: PingParams) -> PingResult:
        # Every packet may wait the full timeout; the margin covers the session itself.
        output = await transport.send(self.ping_command(params), timeout=params.count * params.timeout + 30)
        match = self.SUMMARY.search(output)
        if match is None:
            # IOS explains a ping it couldn't send on a line of its own, e.g. "% Unrecognized host or address".
            reason = next((line.strip() for line in output.splitlines() if line.strip().startswith("%")), None)
            raise DriverException(f"ping {params.target}: {reason or 'the device gave no ping summary'}")
        rtt = {f"rtt_{k}_ms": float(match[k]) if match[k] else None for k in ("min", "avg", "max")}
        return PingResult(sent=int(match["sent"]), received=int(match["received"]), **rtt)

    @staticmethod
    def ping_command(params: PingParams) -> str:
        """`ping [vrf X] target repeat N [size S df-bit] timeout T [source IF]`: a set size always pings
        with don't-fragment, so the path's MTU is what is tested."""
        words = ["ping", *(["vrf", params.vrf] if params.vrf else []), params.target, "repeat", str(params.count)]
        if params.size:
            words += ["size", str(params.size), "df-bit"]
        words += ["timeout", str(params.timeout)]
        if params.source:
            words += ["source", params.source]
        return " ".join(words)
