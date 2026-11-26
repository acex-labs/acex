"""Mock IOS XE SSH server — responds to Scrapli's command set with static configs."""

import asyncio
import hashlib
import ipaddress
import logging
import os
import pathlib
import time

import asyncssh

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("mock-device")

HOSTNAME = os.environ.get("MOCK_HOSTNAME", "mock-router")
# The address to listen on, e.g. a loopback alias like 127.0.0.2 to run several devices on one host.
BIND = os.environ.get("MOCK_BIND", "")
SSH_PORT = int(os.environ.get("SSH_PORT", "22"))
USERNAME = os.environ.get("SSH_USERNAME", "admin")
PASSWORD = os.environ.get("SSH_PASSWORD", "admin")

# Derived from hostname so every mock container gets a stable, unique identity
_HOST_HASH = hashlib.sha256(HOSTNAME.encode()).hexdigest().upper()

OS_NAME = os.environ.get("MOCK_OS", "IOS XE")
OS_VERSION = os.environ.get("MOCK_OS_VERSION", "17.09.04a")
MODEL = os.environ.get("MOCK_MODEL", "C9300-48P")
SERIAL = os.environ.get("MOCK_SERIAL", f"FOC{int(_HOST_HASH[:8], 16) % 10000:04d}{_HOST_HASH[8:12]}")
BASE_MAC = "70:18:a7:" + ":".join(_HOST_HASH[i : i + 2].lower() for i in (12, 14)) + ":00"
START_TIME = time.monotonic()

CONFIG_DIR = pathlib.Path("/configs")
# The running-config to serve; by default the hostname's file in /configs, else default.txt there.
CONFIG_FILE = pathlib.Path(os.environ.get("MOCK_CONFIG", CONFIG_DIR / f"{HOSTNAME}.txt"))
FALLBACK_CONFIG = CONFIG_DIR / "default.txt"
# Each device on a host needs its own key file, somewhere it may write.
HOST_KEY = pathlib.Path(os.environ.get("MOCK_HOST_KEY", "/etc/ssh/mock_host_key"))
# Ping targets that never answer, comma separated; every other target answers every packet.
UNREACHABLE = {t.strip() for t in os.environ.get("MOCK_UNREACHABLE", "").split(",") if t.strip()}
# Delay before every response, in milliseconds, to behave like a device over a real network.
LATENCY = int(os.environ.get("MOCK_LATENCY_MS", "0")) / 1000

SHOW_VERSION_TEMPLATE = (pathlib.Path(__file__).parent / "show_version.txt").read_text()


def _load_config() -> str:
    for path in (CONFIG_FILE, FALLBACK_CONFIG):
        if path.exists():
            return path.read_text()
    return f"hostname {HOSTNAME}\n!\nend\n"


LLDP_EMPTY = "% LLDP is not enabled"
CDP_EMPTY = "% CDP is not enabled"
PROMPT = f"\n{HOSTNAME}#"


def _short_version(version: str) -> str:
    """17.09.04a -> 17.9.4a, as printed on the IOS Software line."""
    return ".".join(part.lstrip("0") or "0" for part in version.split("."))


def _uptime() -> str:
    remaining = int(time.monotonic() - START_TIME) // 60
    parts = []
    for unit, size in (("week", 7 * 24 * 60), ("day", 24 * 60), ("hour", 60), ("minute", 1)):
        value, remaining = divmod(remaining, size)
        if value:
            parts.append(f"{value} {unit}{'s' if value != 1 else ''}")
    return ", ".join(parts) or "0 minutes"


def _show_version() -> str:
    uptime = _uptime()
    return SHOW_VERSION_TEMPLATE.format(
        OS_NAME=OS_NAME,
        OS_VERSION=OS_VERSION,
        SHORT_VERSION=_short_version(OS_VERSION),
        HOSTNAME=HOSTNAME,
        UPTIME=uptime,
        MODEL=MODEL,
        SERIAL=SERIAL,
        BASE_MAC=BASE_MAC,
    )


def _ping(cmd: str) -> str:
    """`ping [vrf X] target [repeat N] [size S] [df-bit] [timeout T] ...` answered as IOS does."""
    words = cmd.split()[1:]
    if words[:1] == ["vrf"]:
        words = words[2:]
    if not words:
        return "% Incomplete command."
    target, options = words[0], dict(zip(words[1::2], words[2::2], strict=False))
    count, size, timeout = int(options.get("repeat", 5)), options.get("size", "100"), options.get("timeout", "2")
    answers = 0 if target in UNREACHABLE else count
    summary = f"Success rate is {answers * 100 // count} percent ({answers}/{count})"
    if answers:
        summary += ", round-trip min/avg/max = 1/2/4 ms"
    return (
        "Type escape sequence to abort.\n"
        f"Sending {count}, {size}-byte ICMP Echos to {target}, timeout is {timeout} seconds:\n"
        + "!" * answers
        + "." * (count - answers)
        + "\n"
        + summary
    )


class Operational:
    """Operational state answered as IOS XE prints it: the MAC address table, ARP, routes, interfaces and
    traceroute. Filters behave as on a device, so a lookup finds or misses, and an unknown VRF or interface
    is refused with IOS's own words."""

    INVALID = "                    ^\n% Invalid input detected at '^' marker."
    VRFS = {"MGMT"}
    OWN_MAC = ".".join(BASE_MAC.replace(":", "")[i : i + 4] for i in (0, 4, 8))
    #: Vlan, MAC, type, ports.
    MACS = [
        ("All", "0100.0ccc.cccc", "STATIC", "CPU"),
        ("All", "0180.c200.0000", "STATIC", "CPU"),
        ("1", OWN_MAC, "STATIC", "Vl1"),
        ("10", "0050.56a1.2b3c", "DYNAMIC", "Gi1/0/1"),
        ("10", "0050.56a1.2b3d", "DYNAMIC", "Gi1/0/2"),
        ("20", "0050.56a1.2b3c", "DYNAMIC", "Gi1/0/1"),
        ("20", "0100.5e00.0001", "STATIC", "Gi1/0/2 Gi1/0/3"),
    ]
    #: Address, age in minutes or "-" for the device's own, MAC or Incomplete, interface.
    ARP = {
        None: [
            ("10.0.0.1", "-", OWN_MAC, "Vlan10"),
            ("10.0.0.2", "12", "0050.56a1.2b3c", "Vlan10"),
            ("10.0.0.3", "0", "Incomplete", ""),
        ],
        "MGMT": [
            ("192.168.100.10", "-", OWN_MAC, "GigabitEthernet0/0"),
            ("192.168.100.1", "3", "0050.56a1.0001", "GigabitEthernet0/0"),
        ],
    }
    ROUTE_TABLE = """\
Codes: L - local, C - connected, S - static, R - RIP, M - mobile, B - BGP
       D - EIGRP, EX - EIGRP external, O - OSPF, IA - OSPF inter area
       N1 - OSPF NSSA external type 1, N2 - OSPF NSSA external type 2
       E1 - OSPF external type 1, E2 - OSPF external type 2, m - OMP
       i - IS-IS, su - IS-IS summary, L1 - IS-IS level-1, L2 - IS-IS level-2
       + - replicated route, % - next hop override, p - overrides from PfR

Gateway of last resort is 10.0.0.254 to network 0.0.0.0

S*    0.0.0.0/0 [1/0] via 10.0.0.254
      10.0.0.0/8 is variably subnetted, 4 subnets, 3 masks
C        10.0.0.0/24 is directly connected, Vlan10
L        10.0.0.1/32 is directly connected, Vlan10
O IA     10.1.0.0/24 [110/2] via 10.0.0.2, 00:12:34, Vlan10
O E2     10.2.0.0/16 [110/20] via 10.0.0.2, 1d02h, Vlan10
                     [110/20] via 10.0.0.3, 1d02h, Vlan10"""
    ROUTE_TABLE_MGMT = """\
Routing Table: MGMT
Gateway of last resort is 192.168.100.1 to network 0.0.0.0

S*    0.0.0.0/0 [1/0] via 192.168.100.1
      192.168.100.0/24 is variably subnetted, 2 subnets, 2 masks
C        192.168.100.0/24 is directly connected, GigabitEthernet0/0
L        192.168.100.10/32 is directly connected, GigabitEthernet0/0"""
    #: The detailed entry of each route in the global table, by prefix.
    ROUTE_ENTRIES = {
        "0.0.0.0/0": """\
Routing entry for 0.0.0.0/0, supernet
  Known via "static", distance 1, metric 0, candidate default path
  Routing Descriptor Blocks:
  * 10.0.0.254
      Route metric is 0, traffic share count is 1""",
        "10.0.0.0/24": """\
Routing entry for 10.0.0.0/24
  Known via "connected", distance 0, metric 0 (connected, via interface)
  Routing Descriptor Blocks:
  * directly connected, via Vlan10
      Route metric is 0, traffic share count is 1""",
        "10.1.0.0/24": """\
Routing entry for 10.1.0.0/24
  Known via "ospf 1", distance 110, metric 2, type inter area
  Last update from 10.0.0.2 on Vlan10, 00:12:34 ago
  Routing Descriptor Blocks:
  * 10.0.0.2, from 10.255.0.1, 00:12:34 ago, via Vlan10
      Route metric is 2, traffic share count is 1""",
        "10.2.0.0/16": """\
Routing entry for 10.2.0.0/16
  Known via "ospf 1", distance 110, metric 20, type extern 2, forward metric 1
  Last update from 10.0.0.2 on Vlan10, 1d02h ago
  Routing Descriptor Blocks:
  * 10.0.0.2, from 10.255.0.1, 1d02h ago, via Vlan10
      Route metric is 20, traffic share count is 1
    10.0.0.3, from 10.255.0.1, 1d02h ago, via Vlan10
      Route metric is 20, traffic share count is 1""",
    }
    #: Each interface's block of `show interfaces`, by name.
    INTERFACES = {
        "GigabitEthernet0/0": """\
GigabitEthernet0/0 is up, line protocol is up
  Description: management
  Full Duplex, 1000Mbps, link type is auto, media type is RJ45
  Input queue: 0/375/0/0 (size/max/drops/flushes); Total output drops: 0
     0 input errors, 0 CRC, 0 frame, 0 overrun, 0 ignored
     0 output errors, 0 collisions, 0 interface resets""",
        "GigabitEthernet1/0/1": """\
GigabitEthernet1/0/1 is up, line protocol is up (connected)
  Description: UPLINK
  Full-duplex, 1000Mb/s, media type is 10/100/1000BaseTX
  Input queue: 0/2000/3/0 (size/max/drops/flushes); Total output drops: 7
     12 input errors, 4 CRC, 0 frame, 0 overrun, 0 ignored
     0 output errors, 0 collisions, 1 interface resets""",
        "GigabitEthernet1/0/2": """\
GigabitEthernet1/0/2 is down, line protocol is down (notconnect)
  Auto-duplex, Auto-speed, media type is 10/100/1000BaseTX
  Input queue: 0/2000/0/0 (size/max/drops/flushes); Total output drops: 0
     0 input errors, 0 CRC, 0 frame, 0 overrun, 0 ignored
     0 output errors, 0 collisions, 0 interface resets""",
        "GigabitEthernet1/0/3": """\
GigabitEthernet1/0/3 is administratively down, line protocol is down (disabled)
  Auto-duplex, Auto-speed, media type is 10/100/1000BaseTX""",
        "GigabitEthernet1/0/4": """\
GigabitEthernet1/0/4 is down, line protocol is down (err-disabled)
  Auto-duplex, Auto-speed, media type is 10/100/1000BaseTX""",
        "TenGigabitEthernet1/1/1": """\
TenGigabitEthernet1/1/1 is up, line protocol is up (connected)
  Full-duplex, 10Gb/s, link type is auto, media type is SFP-10GBase-SR""",
        "Vlan10": """\
Vlan10 is up, line protocol is up , Autostate Enabled
  Description: users
  Input queue: 0/375/0/0 (size/max/drops/flushes); Total output drops: 0""",
    }

    @classmethod
    def answer(cls, cmd: str) -> str | None:
        """The output of an operational command, or None when it is none of them."""
        words = cmd.split()
        if words[:3] == ["show", "mac", "address-table"]:
            return cls.mac_table(words[3:])
        if words[:3] == ["show", "ip", "arp"]:
            return cls.arp(words[3:])
        if words[:3] == ["show", "ip", "route"]:
            return cls.ip_route(words[3:])
        if words[:2] == ["show", "interfaces"]:
            return cls.interfaces(words[2:])
        if words[:1] == ["traceroute"]:
            return cls.traceroute(words[1:])
        return None

    @staticmethod
    def vrf(words: list[str]) -> tuple[str | None, list[str]]:
        return (words[1], words[2:]) if words[:1] == ["vrf"] and len(words) > 1 else (None, words)

    @classmethod
    def mac_table(cls, words: list[str]) -> str:
        filters = dict(zip(words[::2], words[1::2], strict=False))
        rows = [
            row
            for row in cls.MACS
            if ("address" not in filters or row[1] == filters["address"].lower())
            and ("vlan" not in filters or row[0] == filters["vlan"])
            and ("interface" not in filters or filters["interface"] in row[3].split())
        ]
        lines = [f"{vlan:>4}    {mac}    {kind:<8}    {ports}" for vlan, mac, kind, ports in rows]
        return "\n".join(
            [
                "          Mac Address Table",
                "-------------------------------------------",
                "",
                "Vlan    Mac Address       Type        Ports",
                "----    -----------       --------    -----",
                *lines,
                f"Total Mac Addresses for this criterion: {len(lines)}",
            ]
        )

    @classmethod
    def arp(cls, words: list[str]) -> str:
        vrf, words = cls.vrf(words)
        if vrf not in cls.ARP:
            return f"% IP ARP table vrf {vrf} does not exist"
        rows = [row for row in cls.ARP[vrf] if not words or words[0] in (row[0], row[3])]
        lines = [f"Internet  {ip:<16} {age:>5}   {mac:<14}  ARPA   {interface}" for ip, age, mac, interface in rows]
        return "\n".join(["Protocol  Address          Age (min)  Hardware Addr   Type   Interface", *lines])

    @classmethod
    def ip_route(cls, words: list[str]) -> str:
        vrf, words = cls.vrf(words)
        if vrf is not None and vrf not in cls.VRFS:
            return f"% IP routing table {vrf} does not exist"
        if not words:
            return cls.ROUTE_TABLE_MGMT if vrf else cls.ROUTE_TABLE
        if vrf:
            return "% Network not in table"
        networks = [ipaddress.ip_network(prefix) for prefix in cls.ROUTE_ENTRIES]
        if len(words) > 1:
            asked = ipaddress.ip_network(f"{words[0]}/{words[1]}", strict=False)
            found = [network for network in networks if network == asked]
        else:
            found = [network for network in networks if ipaddress.ip_address(words[0]) in network]
        if not found:
            return "% Network not in table"
        return cls.ROUTE_ENTRIES[str(max(found, key=lambda network: network.prefixlen))]

    @classmethod
    def interfaces(cls, words: list[str]) -> str:
        if not words:
            return "\n".join(cls.INTERFACES.values())
        return cls.INTERFACES.get(words[0], cls.INVALID)

    @classmethod
    def traceroute(cls, words: list[str]) -> str:
        """Three hops to the target, or silence after the first when it never answers."""
        _, words = cls.vrf(words)
        target, options = words[0], words[1:]
        probes = int(options[options.index("probe") + 1]) if "probe" in options else 3
        max_ttl = int(options[options.index("ttl") + 2]) if "ttl" in options else 30
        hops = [f"  1 10.0.0.254 {' '.join(['1 msec'] * probes)}"]
        if target in UNREACHABLE:
            hops += [f"{ttl:>3} {' '.join(['*'] * probes)}" for ttl in range(2, max_ttl + 1)]
        else:
            hops += [f"  2 192.0.2.1 {' '.join(['4 msec'] * probes)}", f"  3 {target} {' '.join(['6 msec'] * probes)}"]
        return "\n".join(["Type escape sequence to abort.", f"Tracing the route to {target}", "", *hops])


def _is_show_version(cmd: str) -> bool:
    words = cmd.split()
    return (
        len(words) == 2
        and len(words[0]) >= 2
        and "show".startswith(words[0])
        and len(words[1]) >= 3
        and "version".startswith(words[1])
    )


def _handle(cmd: str) -> str:
    cmd = cmd.strip()
    log.info(f"CMD: {cmd!r}")
    if not cmd or cmd.startswith("terminal"):
        return PROMPT
    elif _is_show_version(cmd):
        return _show_version().rstrip("\n") + PROMPT
    elif cmd.split()[0] == "ping":
        return _ping(cmd) + PROMPT
    elif (operational := Operational.answer(cmd)) is not None:
        return operational + PROMPT
    elif "lldp neighbors" in cmd:
        return LLDP_EMPTY + PROMPT
    elif "cdp neighbors" in cmd:
        return CDP_EMPTY + PROMPT
    else:
        return PROMPT


class CliSession:
    """One SSH session's CLI mode: exec, global configuration, or a configuration submode.

    What is entered in configuration mode is kept for the device's lifetime and
    shows in `show running-config`, so a push can be checked afterwards.
    """

    #: Lines entered in configuration mode since the device started, shared by all sessions.
    pushed: list[str] = []

    #: Commands that enter a configuration submode, by their first word, and the submode's prompt.
    SUBMODES = {"interface": "config-if", "line": "config-line", "router": "config-router", "vlan": "config-vlan"}

    def __init__(self):
        #: None in exec mode, otherwise the mode shown in the prompt, e.g. "config" or "config-if".
        self.mode: str | None = None

    @property
    def prompt(self) -> str:
        return f"\n{HOSTNAME}({self.mode})#" if self.mode else PROMPT

    def handle(self, cmd: str) -> str:
        line = cmd.strip()
        if self.mode is None:
            return self._exec(line, cmd)
        return self._configure(line)

    def _exec(self, line: str, cmd: str) -> str:
        words = line.split()
        if len(words) >= 1 and words[0].startswith("conf") and "configure".startswith(words[0]):
            log.info(f"CMD: {line!r}")
            self.mode = "config"
            return "Enter configuration commands, one per line.  End with CNTL/Z." + self.prompt
        if line in ("write memory", "wr", "copy running-config startup-config"):
            log.info(f"CMD: {line!r}")
            return "Building configuration...\n[OK]" + self.prompt
        if line == "show running-config":
            log.info(f"CMD: {line!r}")
            return self.running_config().rstrip("\n") + self.prompt
        return _handle(cmd)

    def _configure(self, line: str) -> str:
        if not line:
            return self.prompt
        if line == "end":
            self.mode = None
            return self.prompt
        if line == "exit":
            self.mode = None if self.mode == "config" else "config"
            return self.prompt
        log.info(f"CONFIG ({self.mode}): {line!r}")
        submode = self.SUBMODES.get(line.split()[0])
        if submode is not None:
            self.mode = submode
            self.pushed.append(line)
        else:
            # Lines arrive without their indentation; indent those entered in a submode.
            self.pushed.append(f" {line}" if self.mode != "config" else line)
        return self.prompt

    @classmethod
    def running_config(cls) -> str:
        """The configuration file, with what has been entered since appended."""
        base = _load_config().rstrip()
        if not cls.pushed:
            return base + "\n"
        if base.endswith("end"):
            base = base[: -len("end")].rstrip()
        return "\n".join([base, "!", *cls.pushed, "!", "end"]) + "\n"


async def handle_client(process: asyncssh.SSHServerProcess):
    session = CliSession()
    process.stdout.write(PROMPT)
    await process.stdout.drain()

    buf = ""
    async for chunk in process.stdin:
        buf += chunk
        while "\n" in buf or "\r" in buf:
            for sep in ("\r\n", "\n", "\r"):
                if sep in buf:
                    line, buf = buf.split(sep, 1)
                    break
            response = session.handle(line)
            if LATENCY:
                await asyncio.sleep(LATENCY)
            process.stdout.write(response)
            await process.stdout.drain()

    process.exit(0)


class MockSSHServer(asyncssh.SSHServer):
    def begin_auth(self, username):
        return True

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        return username == USERNAME and password == PASSWORD


async def main():
    key_path = HOST_KEY
    if not key_path.exists():
        key = asyncssh.generate_private_key("ssh-rsa")
        key.write_private_key(str(key_path))

    server_key = asyncssh.read_private_key(str(key_path))

    await asyncssh.create_server(
        MockSSHServer,
        host=BIND,
        port=SSH_PORT,
        server_host_keys=[server_key],
        process_factory=handle_client,
    )
    log.info(f"Mock IOS XE device '{HOSTNAME}' listening on {BIND or '*'}:{SSH_PORT}, serving {CONFIG_FILE}")
    await asyncio.get_event_loop().create_future()


asyncio.run(main())
