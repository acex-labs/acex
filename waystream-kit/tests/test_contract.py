import ipaddress
import json
import re
import tomllib

import pytest

from ibos_kit import evidence
from ibos_kit.accounting import expected_unmatched, lines_with_parents
from ibos_kit.mock.engine import Session
from ibos_kit.mock.scenarios import PROFILES, device_for
from ibos_kit.paths import DEVICE_FIXTURES, FIXTURES, GOLDEN, VARIANTS
from tests.oracles import interface_blocks, normalize

MANIFEST = tomllib.loads((FIXTURES / "manifest.toml").read_text())["fixture"]
ALLOWED_NETWORKS = [
    ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "224.0.0.0/4")
]
ALLOWED_OTHER = {"0.0.0.0", "0.0.0.200"}
MAC = re.compile(r"\b[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}\b")
CUSTOMER = "".join(["we", "x", "net"])


def all_fixture_files():
    return sorted(p for p in FIXTURES.rglob("*") if p.is_file() and p.name != "manifest.toml")


def test_every_fixture_is_in_the_manifest_and_every_manifest_entry_has_a_file():
    listed = {e["path"] for e in MANIFEST}
    on_disk = {str(p.relative_to(FIXTURES)) for p in all_fixture_files()}
    assert listed == on_disk


def test_manifest_facts_exist_and_assumed_layouts_are_named_as_such():
    register = evidence.load()
    for entry in MANIFEST:
        assert set(entry["facts"]) <= set(register.facts), entry["path"]
        assert (".assumed" in entry["path"]) <= (entry["layout"] == "assumed"), entry["path"]


@pytest.mark.parametrize("path", all_fixture_files(), ids=lambda p: str(p.relative_to(FIXTURES)))
def test_fixtures_hold_only_made_up_addresses_names_and_macs(path):
    text = path.read_text()
    assert CUSTOMER not in text.lower()
    for match in re.finditer(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text):
        value = match.group()
        if value in ALLOWED_OTHER or value.startswith("255.") or value == "0.0.0.0":
            continue
        address = ipaddress.ip_address(value)
        assert any(address in network for network in ALLOWED_NETWORKS), f"{path.name}: {value}"
    for mac in MAC.findall(text):
        assert mac.startswith(("0200.5e", "0008.ae00", "0000.0000")), f"{path.name}: {mac}"
    if "secret" in path.name or path.parent == VARIANTS:
        return
    assert not re.search(r"(?i)password|secret|community", text.replace("EXAMPLE-", "")) or path.parent == GOLDEN


def test_secret_values_in_variants_are_all_marked_as_examples():
    for path in (VARIANTS / "with-secrets.txt", VARIANTS / "invented-secret-syntax.txt"):
        values = re.findall(r"(?:community|secret|password|key) (?:\d )?(\S+)", path.read_text())
        assert values and all(v.startswith("EXAMPLE-") or v in {"read-only", "trap"} for v in values), values


@pytest.mark.parametrize("key", sorted(PROFILES))
def test_the_mock_serves_each_fixture_unchanged_and_the_fixtures_agree_with_the_profile(key):
    device = device_for(key)
    profile = device.profile
    session = Session(device)
    session.mode = "privileged"
    for command in profile.commands:
        if "<interface>" in command.words:
            continue
        served = session.handle(" ".join(command.words)).text
        assert served == (DEVICE_FIXTURES / command.fixture).read_text().rstrip("\n"), command.words
    config = device.running_config
    if config:
        assert f"\nhostname {profile.hostname}\n" in config
        assert config.startswith(f"! version {profile.firmware} ({profile.firmware}.bz2)\n")
        assert config.rstrip().endswith("!end")
    version = session.handle("show version").text
    assert profile.firmware in version and profile.model in version
    assert f"{profile.hostname} uptime is" in version or "Version 7." in version


@pytest.mark.parametrize(
    ("raw", "golden"),
    [
        ("device/ms4000-6.3.5/running-config.txt", "ms4000-6.3.5.normalized.txt"),
        ("device/ms4000-6.3.5/running-config.with-client.txt", "ms4000-6.3.5.with-client.normalized.txt"),
        ("device/asr6000-6.3.5/running-config.txt", "asr6000-6.3.5.normalized.txt"),
        ("device/asr6000-6.3.5/running-config.with-client.txt", "asr6000-6.3.5.with-client.normalized.txt"),
    ],
)
def test_the_normalized_goldens_are_what_the_plain_oracle_makes_of_the_fixtures(raw, golden):
    assert normalize((FIXTURES / raw).read_text()) == (GOLDEN / golden).read_text()


def test_normalizing_makes_a_configuration_with_a_client_equal_to_one_without():
    for name in ("ms4000-6.3.5", "asr6000-6.3.5"):
        clean = (GOLDEN / f"{name}.normalized.txt").read_text()
        assert clean == (GOLDEN / f"{name}.with-client.normalized.txt").read_text()


@pytest.mark.parametrize("name", ["asr6000-6.3.5", "ms4000-6.3.5"])
def test_the_parsed_goldens_describe_lines_that_exist_in_the_normalized_text(name):
    golden = json.loads((GOLDEN / f"{name}.parsed.json").read_text())
    text = (GOLDEN / golden["from"]).read_text()
    assert f"hostname {golden['hostname']}" in text.splitlines()
    for interface in golden["interfaces"]:
        assert f"interface {interface}" in text.splitlines()
    present = {(line, parents) for line, parents in lines_with_parents(text)}
    for entry in golden["must_be_unmatched"]:
        assert (entry["line"], tuple(entry["parents"])) in present, entry
    assert {(e["line"], tuple(e["parents"])) for e in golden["must_be_unmatched"]} <= set(expected_unmatched(text))


def test_a_port_without_a_no_shutdown_line_is_disabled_because_shutdown_is_the_default_state():
    golden = json.loads((GOLDEN / "ms4000-6.3.5.parsed.json").read_text())
    assert golden["interfaces"]["tengigabitethernet1"]["enabled"] is False
    assert golden["interfaces"]["gigabitethernet21"]["enabled"] is True


@pytest.mark.parametrize("name", ["asr6000-6.3.5", "ms4000-6.3.5"])
def test_the_parsed_goldens_agree_with_the_text_they_describe_line_by_line(name):
    golden = json.loads((GOLDEN / f"{name}.parsed.json").read_text())
    blocks = interface_blocks((GOLDEN / golden["from"]).read_text())
    assert set(golden["interfaces"]) == set(blocks)
    for interface, expected in golden["interfaces"].items():
        lines = blocks[interface]
        descriptions = [line.removeprefix("description ") for line in lines if line.startswith("description ")]
        assert expected["description"] == (descriptions[0] if descriptions else None), interface
        assert expected["enabled"] == ("no shutdown" in lines), interface
        addresses = [line.split() for line in lines if line.startswith("ip address ")]
        if addresses:
            ip, mask = addresses[0][2:4]
            assert expected["ipv4"] == f"{ip}/{ipaddress.ip_network(f'{ip}/{mask}', strict=False).prefixlen}"
        else:
            assert expected["ipv4"] is None
