import re

from acex_devkit.models.actions import TracerouteHop, TracerouteParams, TracerouteProbe, TracerouteResult

from .text import IOSText


class Traceroute:
    """`traceroute [vrf V] target numeric timeout T probe P ttl 1 M [source IF]`.

    ```
    Tracing the route to 8.8.8.8
      1 10.0.0.1 1 msec 1 msec 1 msec
      2 192.0.2.1 [MPLS: Label 16 Exp 0] 5 msec
        192.0.2.5 6 msec 5 msec
      3 * * *
      4 198.51.100.1 !H  *  !H
    ```

    Each hop's probes follow the address that answered them; a line that starts with an address instead of a
    hop number continues the hop above with another address.
    """

    DESTINATION = re.compile(rf"Tracing the route to (?:\S+ \()?(?P<address>{IOSText.IP})")
    HOP = re.compile(r"^\s*(?P<ttl>\d+)\s+(?P<probes>\S.*)$")
    MORE = re.compile(rf"^\s+(?P<probes>{IOSText.IP}\s.*)$")
    ANNOTATION = re.compile(r"\[[^\]]*\]")
    ADDRESS = re.compile(IOSText.IP)
    RTT = re.compile(r"\d+(?:\.\d+)?")
    UNREACHABLE = {"!H": "host", "!N": "network", "!P": "protocol", "!A": "admin"}

    @staticmethod
    def command(params: TracerouteParams) -> str:
        words = ["traceroute", *(["vrf", params.vrf] if params.vrf else []), params.target, "numeric"]
        words += ["timeout", str(params.timeout), "probe", str(params.probes), "ttl", "1", str(params.max_hops)]
        if params.source:
            words += ["source", params.source]
        return " ".join(words)

    @staticmethod
    def timeout(params: TracerouteParams) -> int:
        """Every probe to every hop may wait the full timeout; the margin covers the session itself."""
        return params.max_hops * params.probes * params.timeout + 30

    @classmethod
    def parse(cls, output: str) -> TracerouteResult:
        destination = cls.DESTINATION.search(output)
        hops: list[TracerouteHop] = []
        for line in output.splitlines():
            if hop := cls.HOP.match(line):
                hops.append(TracerouteHop(ttl=int(hop["ttl"]), probes=cls.probes(hop["probes"])))
            elif hops and (more := cls.MORE.match(line)):
                hops[-1].probes.extend(cls.probes(more["probes"]))
        return TracerouteResult(destination=destination["address"] if destination else None, hops=hops)

    @classmethod
    def probes(cls, text: str) -> list[TracerouteProbe]:
        probes: list[TracerouteProbe] = []
        address = None
        for word in cls.ANNOTATION.sub(" ", text).split():
            if cls.ADDRESS.fullmatch(word):
                address = word
            elif word == "*":
                probes.append(TracerouteProbe())
            elif word.startswith("!"):
                probes.append(TracerouteProbe(address=address, unreachable=cls.UNREACHABLE.get(word, "other")))
            elif cls.RTT.fullmatch(word):
                probes.append(TracerouteProbe(address=address, rtt_ms=float(word)))
        return probes
