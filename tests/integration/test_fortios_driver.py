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


def a_session_printing(output, name="FGT-1"):
    """What a FortiOS session prints for `run`: a prompt before each of the seven lines it is typed (the lines are not
    echoed), the output of the command following the fourth."""
    before = f"{name} # \n{name} (console) # \n{name} (console) # \n{name} # "
    after = f"\n{name} # \n{name} (console) # \n{name} (console) # \n{name} # "
    return before + output + after


class FakeConnection:
    """What `asyncssh.connect` returns: a typed-in script that holds a command of `printing` is answered the way a
    session prints that command's output, any other by `answers`, keyed by the command (None for a session)."""

    def __init__(self, answers=None, printing=None):
        self.answers = answers or {}
        self.printing = printing or {}
        self.runs = []

    async def run(self, command, input=None, check=True):
        self.runs.append((command, input))
        for line in (input or "").splitlines():
            if line in self.printing:
                return SimpleNamespace(stdout=a_session_printing(self.printing[line]))
        return SimpleNamespace(stdout=self.answers.get(command, ""))


def transport_on(connection):
    transport = fortios.FortiOSTransport("10.0.0.1", [LOGIN])
    transport.conn = connection
    return transport


def test_the_configuration_is_read_in_a_session_with_the_pager_off_and_back_on():
    connection = FakeConnection(printing={"show full-configuration": SHOW_FULL_CONFIGURATION})

    config = asyncio.run(transport_on(connection).get_config())

    assert config == SHOW_FULL_CONFIGURATION
    assert connection.runs == [
        (
            None,
            "config system console\nset output standard\nend\n"
            "show full-configuration\n"
            "config system console\nset output more\nend\nexit\n",
        )
    ]


def test_each_command_runs_in_its_own_session_and_answers_in_order():
    connection = FakeConnection(printing={"get system status": "status\n", "get system performance status": "perf\n"})

    answers = asyncio.run(transport_on(connection).execute(["get system status", "get system performance status"]))

    assert answers == ["status\n", "perf\n"]
    assert len(connection.runs) == 2


def test_the_output_is_cut_out_between_the_prompts_even_when_a_line_in_it_looks_like_one():
    output = "config firewall policy\n    set comment x\nbanner # not a prompt\nend\n"
    connection = FakeConnection(printing={"show full-configuration": output})

    assert asyncio.run(transport_on(connection).get_config()) == output


def test_what_cannot_be_told_from_a_session_is_an_error_that_carries_what_the_device_printed():
    connection = FakeConnection(answers={None: "Permission denied"})

    with pytest.raises(DriverException) as caught:
        asyncio.run(transport_on(connection).get_config())

    assert "Permission denied" in str(caught.value)


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


def test_a_command_that_does_not_finish_is_a_connection_timeout(monkeypatch):
    class Stuck:
        async def run(self, command, input=None, check=True):
            await asyncio.sleep(10)

    transport = transport_on(Stuck())
    monkeypatch.setattr(transport, "COMMAND_TIMEOUT", 0.01)

    with pytest.raises(ConnectionTimeout):
        asyncio.run(transport.execute(["get system status"]))
