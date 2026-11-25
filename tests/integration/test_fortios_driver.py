"""What the FortiOS driver takes on, how it frames text for the mapper, and how it reads, masks and reaches a device."""

import asyncio
from types import SimpleNamespace

import pytest
from acex_devkit.configdiffer import ConfigDiffer
from acex_devkit.exceptions import (
    AuthenticationFailed,
    ConnectionTimeout,
    DriverException,
    HostUnreachable,
    SshAlgorithmMismatch,
)
from acex_devkit.models.asset import Asset
from acex_devkit.models.codec_result import Span
from acex_devkit.models.composed_configuration import ComposedConfiguration, System, SystemConfig
from acex_devkit.models.credential import CredentialSecret
from acex_devkit.models.platform import OS, Vendor
from acex_driver_fortinet_fortios_cli import framing
from acex_driver_fortinet_fortios_cli.codec import FortiOSCodec
from acex_driver_fortinet_fortios_cli.fortios_cli import FortiOSCLIDriver
from acex_driver_fortinet_fortios_cli.normalizer import FortiOSNormalizer
from acex_driver_fortinet_fortios_cli.state import FortiOSState
from acex_driver_fortinet_fortios_cli.transport import transport as fortios
from asyncssh import KeyExchangeFailed, PermissionDenied

LOGIN = CredentialSecret(id=1, credential_type="userpass", fields={"username": "admin", "password": "pw"})

SHOW_FULL_CONFIGURATION = """\
#config-version=FGVM64-7.4.2-FW-build2571-230918:opmode=0:vdom=0:user=admin
#conf_file_ver=3139552461271467
#buildno=2571
#global_vdom=1
config system global
    set admintimeout 30
    set hostname "FGT-1"
    set timezone 26
end
config system interface
    edit "port1"
        set vdom "root"
        set ip 192.168.1.99 255.255.255.0
        config ipv6
            set ip6-mode static
        end
    next
    edit "port2"
        set vdom "root"
    next
end
"""

# The same configuration as the mapper holds it: one space a level and no closing lines.
MAPPER_TEXT = """\
config system interface
 edit "port1"
  set vdom "root"
  config ipv6
   set ip6-mode static
 edit "port2"
  set vdom "root"
config system global
 set hostname "FGT-1"
"""

FORTIOS_TEXT = """\
config system interface
    edit "port1"
        set vdom "root"
        config ipv6
            set ip6-mode static
        end
    next
    edit "port2"
        set vdom "root"
    next
end
config system global
    set hostname "FGT-1"
end
"""


def fortinet_asset(os: OS) -> Asset:
    return Asset(vendor=Vendor.fortinet, serial_number="FGVM01", os=os, hardware_model="FortiGate-VM64-KVM")


def test_the_driver_takes_fortios_assets_only():
    driver = FortiOSCLIDriver()

    assert driver.supports(fortinet_asset(OS.fortinet_fortios))
    assert not driver.supports(
        Asset(vendor=Vendor.cisco, serial_number="FOC1", os=OS.cisco_iosxe, hardware_model="C9300-24P")
    )


def test_the_driver_lists_what_it_does_for_a_fortigate():
    capabilities = FortiOSCLIDriver().capabilities

    assert {(p.vendor, p.os) for p in capabilities.platforms} == {(Vendor.fortinet, OS.fortinet_fortios)}
    assert set(capabilities.operations) == {"get_config", "apply", "execute"}
    assert capabilities.configuration == ["system.config"]


def test_closing_lines_and_four_space_indents_are_added_to_the_mappers_text():
    assert framing.insert(MAPPER_TEXT).text == FORTIOS_TEXT


def test_closing_lines_and_four_space_indents_are_taken_from_fortios_text():
    assert framing.remove(FORTIOS_TEXT).text == MAPPER_TEXT


def test_text_that_has_been_through_both_directions_is_unchanged():
    without_header = SHOW_FULL_CONFIGURATION.split("\n", 4)[4]

    assert framing.insert(framing.remove(without_header).text).text == without_header


def test_a_span_takes_in_the_closing_lines_of_what_it_holds():
    layout = framing.insert(MAPPER_TEXT)
    interfaces = Span(start=1, end=7, path=["interfaces"])
    port1 = Span(start=2, end=5, path=["interfaces", "port1"])
    ipv6 = Span(start=4, end=5, path=["interfaces", "port1", "ipv6"])
    hostname = Span(start=9, end=9, path=["system", "config", "hostname"])

    # Lines of the FortiOS text: 1 config, 2 edit port1, 3 set vdom, 4 config ipv6, 5 set, 6 end, 7 next, 8 edit port2,
    # 9 set vdom, 10 next, 11 end, 12 config system global, 13 set hostname, 14 end.
    assert layout.span(interfaces) == Span(start=1, end=11, path=["interfaces"])
    assert layout.span(port1) == Span(start=2, end=7, path=["interfaces", "port1"])
    assert layout.span(ipv6) == Span(start=4, end=6, path=["interfaces", "port1", "ipv6"])
    assert layout.span(hostname) == Span(start=13, end=13, path=["system", "config", "hostname"])


def test_a_span_read_from_fortios_text_points_at_the_same_lines_when_the_text_is_framed_again():
    layout = framing.remove(FORTIOS_TEXT)

    port1 = Span(start=2, end=5, path=["interfaces", "port1"])

    assert layout.span(port1) == Span(start=2, end=7, path=["interfaces", "port1"])


def test_the_hostname_is_written_the_way_fortios_writes_it():
    config = ComposedConfiguration(system=System(config=SystemConfig(hostname="FGT-1")))

    result = FortiOSCodec().render(config, None)

    assert result.payload == 'config system global\n    set hostname "FGT-1"\nend'
    assert result.metadata.spans == [
        Span(start=1, end=3, path=["system", "config"]),
        Span(start=2, end=2, path=["system", "config", "hostname"]),
    ]


def test_the_hostname_is_read_from_show_full_configuration():
    result = FortiOSCodec().parse(SHOW_FULL_CONFIGURATION, None)

    assert result.configuration.system.config.hostname.value == "FGT-1"
    assert result.metadata.spans == [Span(start=1, end=5, path=["system", "config"])]


def test_what_is_written_reads_back_the_same():
    config = ComposedConfiguration(system=System(config=SystemConfig(hostname="FGT-1")))
    codec = FortiOSCodec()

    read = codec.parse(codec.render(config, None).payload, None).configuration

    assert read.system.config.hostname.value == "FGT-1"
    assert ConfigDiffer().diff(desired_config=config, observed_config=read).get_all_changes() == []


def test_lines_the_syntax_has_no_field_for_are_unmatched_with_the_indent_the_device_wrote():
    result = FortiOSCodec().parse(SHOW_FULL_CONFIGURATION, None)

    unmatched = [(entry.line, entry.parents) for entry in result.metadata.unmatched]

    assert ("    set admintimeout 30", ["config system global"]) in unmatched
    assert ('        set vdom "root"', ["config system interface", '    edit "port1"']) in unmatched
    assert not any(line.strip() in framing.CLOSERS for line, _ in unmatched)


def test_a_patch_leaves_every_change_unrendered_until_fortios_removals_are_written():
    desired = ComposedConfiguration(system=System(config=SystemConfig(hostname="FGT-2")))
    observed = FortiOSCodec().parse(SHOW_FULL_CONFIGURATION, None).configuration
    diff = ConfigDiffer().diff(desired_config=desired, observed_config=observed)

    result = FortiOSCodec().render_patch(diff, None)

    assert result.payload == ""
    assert result.metadata.unrendered == [["system", "config"]]


def test_the_header_the_device_writes_ahead_of_the_configuration_is_dropped():
    normalized = FortiOSCodec().normalize(SHOW_FULL_CONFIGURATION)

    assert normalized.startswith("config system global\n")
    assert "#" not in normalized


MASKED = """\
config system admin
    edit "admin"
        set password ENC <REDACTED>
    next
end
config user radius
    edit "radius1"
        set secret <REDACTED>
        set server "10.1.1.9"
    next
end
config vpn certificate local
    edit "Fortinet_Factory"
        set private-key "<REDACTED>"
        set comments "kept"
    next
end
"""

UNMASKED = """\
config system admin
    edit "admin"
        set password ENC SH2abcdefghijklmnopqrstuvwxyz==
    next
end
config user radius
    edit "radius1"
        set secret mysecret
        set server "10.1.1.9"
    next
end
config vpn certificate local
    edit "Fortinet_Factory"
        set private-key "-----BEGIN ENCRYPTED PRIVATE KEY-----
MIIFDjBABgkqhkiG9w0BBQ0wMzAbBgkqhkiG9w0BBQwwDgQIabc
-----END ENCRYPTED PRIVATE KEY-----"
        set comments "kept"
    next
end
"""


def test_secrets_are_masked_and_the_rest_of_the_line_and_the_configuration_are_kept():
    assert FortiOSCodec().mask(UNMASKED) == MASKED


def test_masking_twice_changes_nothing():
    once = FortiOSCodec().mask(UNMASKED)

    assert FortiOSCodec().mask(once) == once


def test_a_configuration_without_secrets_is_not_changed_by_masking():
    clean = framing.insert(MAPPER_TEXT).text

    assert FortiOSNormalizer().mask(clean).config == clean


GET_SYSTEM_STATUS = """\
Version: FortiGate-VM64-KVM v7.4.2,build2571,230918 (GA.F)
Virus-DB: 92.08647(2023-09-18 00:08)
Serial-Number: FGVMEVABCDEF1234
BIOS version: 04000002
Hostname: FGT-1
Operation Mode: NAT
"""


def test_the_facts_are_read_from_get_system_status():
    async def execute(commands):
        assert commands == ["get system status"]
        return [GET_SYSTEM_STATUS]

    facts = asyncio.run(FortiOSState().get_facts(SimpleNamespace(execute=execute)))

    assert (facts.vendor, facts.os) == (Vendor.fortinet, OS.fortinet_fortios)
    assert facts.os_version == "7.4.2"
    assert facts.hardware_model == "FortiGate-VM64-KVM"
    assert facts.serial_number == "FGVMEVABCDEF1234"


def open_failing_with(monkeypatch, error):
    async def connect(*args, **kwargs):
        raise error

    monkeypatch.setattr(fortios.asyncssh, "connect", connect)
    asyncio.run(fortios.FortiOSTransport("10.0.0.1", [LOGIN]).open())


@pytest.mark.parametrize(
    ("error", "raised"),
    [
        (PermissionDenied("Permission denied"), AuthenticationFailed),
        (KeyExchangeFailed("No matching key exchange algorithm found"), SshAlgorithmMismatch),
        (TimeoutError("timed out"), ConnectionTimeout),
        (ConnectionRefusedError(61, "Connect call failed"), HostUnreachable),
        (OSError(113, "No route to host"), HostUnreachable),
    ],
    ids=lambda value: type(value).__name__ if isinstance(value, Exception) else value.__name__,
)
def test_an_error_while_opening_is_raised_as_the_devkit_error_for_it(monkeypatch, error, raised):
    with pytest.raises(raised) as caught:
        open_failing_with(monkeypatch, error)

    assert type(caught.value) is raised


class FakeConnection:
    """What `asyncssh.connect` returns for a configuration: a script typed into a session is answered by `answers`,
    keyed by the command (None for a session)."""

    def __init__(self, answers=None):
        self.answers = answers or {}
        self.runs = []

    async def run(self, command, input=None, check=True):
        self.runs.append((command, input))
        return SimpleNamespace(stdout=self.answers.get(command, ""))


class FakeFortiOS:
    """What `asyncssh.connect` returns for a unit that is read: each `create_process` is a CLI session that prints a
    prompt and takes a command line. The output is printed `page` lines at a time; after each page but the last the
    pager prints `--More--` and waits for a key, which it echoes and erases the way FortiOS does. `exit` ends the
    session. With `pager=False` the output is printed at once."""

    def __init__(self, outputs, page=3, name="FGT-1", pager=True, cut_after=None, keys_taken=True, split_after=None):
        self.outputs = outputs
        self.page = page
        self.name = name
        self.pager = pager
        self.cut_after = cut_after
        self.keys_taken = keys_taken
        self.split_after = split_after
        self.sessions = []

    async def create_process(self, **kwargs):
        session = FakeSession(self)
        self.sessions.append(session)
        return session


class FakeSession:
    def __init__(self, device):
        self.device = device
        self.typed = []
        self.writes = []
        self.keys = 0
        self.closed = False
        self.stdin = self
        self.stdout = self
        self._out = asyncio.Queue()
        self._in = bytearray()
        self._wake = asyncio.Event()
        self._task = asyncio.ensure_future(self._serve())

    # stdin
    def write(self, data):
        self.writes.append(data)
        self._in.extend(data)
        self._wake.set()

    # stdout
    async def read(self, n):
        return await self._out.get()

    def close(self):
        self.closed = True
        self._task.cancel()

    @property
    def lines(self):
        """What was typed, line by line, without the keys left over in front of a line."""
        return [line.strip() for line in b"".join(self.writes).decode().split("\n") if line.strip()]

    def _say(self, text):
        if text:
            self._out.put_nowait(text.encode())

    async def _byte(self):
        while not self._in:
            self._wake.clear()
            await self._wake.wait()
        return self._in.pop(0)

    async def _line(self):
        line = bytearray()
        while True:
            byte = await self._byte()
            if byte == ord("\n"):
                return line.decode().strip()
            line.append(byte)

    async def _serve(self):
        d = self.device
        prompt = f"{d.name} # "
        self._say(prompt)
        while True:
            command = await self._line()
            self.typed.append(command)
            if command == "exit":
                self._out.put_nowait(b"")
                return
            lines = d.outputs.get(command, "Unknown action 0\n").splitlines(keepends=True)
            step = d.page if d.pager else max(len(lines), 1)
            pages = [lines[i : i + step] for i in range(0, len(lines), step)] or [[]]
            for number, page in enumerate(pages):
                text = "".join(page)
                if d.split_after and d.split_after in text:
                    head, _, rest = text.partition(d.split_after)
                    self._say(head + d.split_after)
                    await asyncio.sleep(0.02)
                    text = rest
                self._say(text)
                if number < len(pages) - 1:
                    self._say("--More-- ")
                    if d.cut_after == number:
                        self._out.put_nowait(b"")
                        return
                    if d.keys_taken:
                        await self._byte()
                        self.keys += 1
                        self._say(" \r         \r")
                    else:
                        await asyncio.sleep(3600)
            self._say(prompt)


def transport_on(connection):
    transport = fortios.FortiOSTransport("10.0.0.1", [LOGIN])
    transport.conn = connection
    return transport


LONG_CONFIGURATION = "".join(
    [SHOW_FULL_CONFIGURATION.split("config system global")[0]]
    + [
        f'config firewall address\n    edit "host-{n}"\n        set subnet 10.0.{n // 250}.{n % 250} 255.255.255.255\n'
        "    next\nend\n"
        for n in range(300)
    ]
    + ['config system global\n    set hostname "FGT-1"\nend\n']
)


def test_a_configuration_is_read_with_the_pager_answered_and_nothing_changed_in_the_device():
    unit = FakeFortiOS({"show full-configuration": SHOW_FULL_CONFIGURATION}, page=4)

    config = asyncio.run(transport_on(unit).get_config())

    assert config == SHOW_FULL_CONFIGURATION
    assert [s.lines for s in unit.sessions] == [["show full-configuration", "exit"]]
    assert unit.sessions[0].keys == len(SHOW_FULL_CONFIGURATION.splitlines()) // 4


def test_a_long_configuration_is_read_whole_and_the_keys_for_its_pages_are_sent_in_batches():
    unit = FakeFortiOS({"show full-configuration": LONG_CONFIGURATION}, page=7)

    config = asyncio.run(transport_on(unit).get_config())

    pages = len(LONG_CONFIGURATION.splitlines()) // 7
    assert config == LONG_CONFIGURATION
    assert unit.sessions[0].keys == pages
    assert len(unit.sessions[0].writes) < pages // 4


def test_a_command_that_fits_on_one_page_is_not_given_a_key():
    unit = FakeFortiOS(
        {"get system status": "Version: FortiGate-VM64 v7.4.2,build2571\nSerial-Number: FGVM01\n"}, page=40
    )

    assert asyncio.run(transport_on(unit).execute(["get system status"])) == [
        "Version: FortiGate-VM64 v7.4.2,build2571\nSerial-Number: FGVM01\n"
    ]
    assert unit.sessions[0].keys == 0


def test_each_command_runs_in_its_own_session_and_answers_in_order():
    unit = FakeFortiOS({"get system status": "status\n", "get system performance status": "perf\n"})

    answers = asyncio.run(transport_on(unit).execute(["get system status", "get system performance status"]))

    assert answers == ["status\n", "perf\n"]
    assert [s.lines for s in unit.sessions] == [
        ["get system status", "exit"],
        ["get system performance status", "exit"],
    ]


def test_a_line_in_the_output_that_looks_like_a_prompt_is_not_taken_for_the_end():
    output = SHOW_FULL_CONFIGURATION.replace("end\nconfig system interface", "end\nFGT-1 # \nconfig system interface")
    unit = FakeFortiOS({"show full-configuration": output}, pager=False, split_after="FGT-1 # ")

    assert asyncio.run(transport_on(unit).get_config()) == output


def test_a_session_that_ends_before_the_output_is_complete_is_an_error_that_carries_what_was_printed():
    unit = FakeFortiOS({"show full-configuration": SHOW_FULL_CONFIGURATION}, page=4, cut_after=1)

    with pytest.raises(DriverException) as caught:
        asyncio.run(transport_on(unit).get_config())

    assert "ended the session before the output was complete" in str(caught.value)
    assert "config-version" not in str(caught.value) or "--More--" in str(caught.value)


def test_a_pager_that_takes_no_keys_is_a_timeout(monkeypatch):
    unit = FakeFortiOS({"get system status": "a\nb\nc\nd\n"}, page=2, keys_taken=False)
    transport = transport_on(unit)
    monkeypatch.setattr(transport, "COMMAND_TIMEOUT", 0.3)
    monkeypatch.setattr(fortios, "STUCK", 0.05)

    with pytest.raises(ConnectionTimeout):
        asyncio.run(transport.execute(["get system status"]))

    assert len(unit.sessions[0].writes) > 1


def test_a_marker_of_the_pager_left_in_the_output_is_an_error():
    unit = FakeFortiOS({"get system status": "Version: x\n--More--\nSerial-Number: y\n"}, pager=False)

    with pytest.raises(DriverException) as caught:
        asyncio.run(transport_on(unit).execute(["get system status"]))

    assert "cut off by the pager" in str(caught.value)


def test_a_session_that_does_not_answer_is_a_connection_timeout(monkeypatch):
    class Silent:
        async def create_process(self, **kwargs):
            return SimpleNamespace(
                stdin=SimpleNamespace(write=lambda data: None),
                stdout=SimpleNamespace(read=lambda n: asyncio.sleep(10)),
                close=lambda: None,
            )

    transport = transport_on(Silent())
    monkeypatch.setattr(transport, "COMMAND_TIMEOUT", 0.01)

    with pytest.raises(ConnectionTimeout):
        asyncio.run(transport.execute(["get system status"]))


MULTI_VDOM_HEADER = "#config-version=FGVM64-7.4.2-FW-build2571-230918:opmode=1:vdom=1:user=admin"


@pytest.mark.parametrize(
    ("config", "said"),
    [
        ("config system global\nend\n", "does not begin with its header"),
        ("", "does not begin with its header"),
        (
            SHOW_FULL_CONFIGURATION.rsplit("    next\nend", 1)[0] + "    next\n",
            "does not end where a configuration ends",
        ),
        (MULTI_VDOM_HEADER + "\nconfig vdom\nedit root\nconfig system interface\nend\n", "has no global part"),
    ],
)
def test_a_configuration_that_is_not_whole_is_an_error_and_never_returned(config, said):
    unit = FakeFortiOS({"show full-configuration": config})

    with pytest.raises(DriverException) as caught:
        asyncio.run(transport_on(unit).get_config())

    assert said in str(caught.value)


def test_a_unit_with_vdoms_is_read_whole_when_its_global_part_is_there():
    config = MULTI_VDOM_HEADER + "\nconfig vdom\nedit root\nnext\nend\nconfig global\nconfig system global\nend\nend\n"
    unit = FakeFortiOS({"show full-configuration": config}, page=2)

    assert asyncio.run(transport_on(unit).get_config()) == config


def test_a_configuration_is_typed_into_a_session_without_blank_lines():
    connection = FakeConnection({})

    asyncio.run(transport_on(connection).apply('config system global\n\n    set hostname "FGT-1"  \nend\n'))

    assert connection.runs == [(None, 'config system global\n    set hostname "FGT-1"\nend\nexit\n')]


def test_an_empty_configuration_is_not_sent():
    connection = FakeConnection({})

    assert asyncio.run(transport_on(connection).apply("\n  \n")) == ""
    assert connection.runs == []


@pytest.mark.parametrize(
    "answer",
    [
        "command parse error before 'hostnam'\nCommand fail. Return code -61",
        "node_check_object fail! for hostname a b\n\nvalue parse error before 'a b'\nCommand fail. Return code -651",
        "Unknown action 0",
    ],
)
def test_a_configuration_the_device_rejects_is_an_error_that_carries_what_it_said(answer):
    connection = FakeConnection({None: answer})

    with pytest.raises(DriverException) as caught:
        asyncio.run(transport_on(connection).apply('config system global\n    set hostnam "x"\nend'))

    assert answer in str(caught.value)


def test_a_configuration_that_does_not_finish_is_a_connection_timeout(monkeypatch):
    class Stuck:
        async def run(self, command, input=None, check=True):
            await asyncio.sleep(10)

    transport = transport_on(Stuck())
    monkeypatch.setattr(transport, "CONFIG_TIMEOUT", 0.01)

    with pytest.raises(ConnectionTimeout):
        asyncio.run(transport.apply('config system global\n    set hostname "x"\nend'))
