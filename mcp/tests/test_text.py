from acex_mcp.text import filter_section, prepare

CONFIG = """\
hostname SW-CORE-01
!
vlan 100
 name USERS
!
vlan 200
 name SERVERS
!
interface GigabitEthernet1/0/1
 description uplink
 switchport access vlan 100
!
interface GigabitEthernet1/0/2
 switchport access vlan 200
"""


def test_section_keeps_the_matching_block():
    out, matched = filter_section(CONFIG, "vlan 100")
    assert matched
    assert "vlan 100" in out
    assert "name SERVERS" not in out


def test_section_keeps_children_of_a_match():
    out, _ = filter_section(CONFIG, "GigabitEthernet1/0/1")
    assert "description uplink" in out
    assert "switchport access vlan 100" in out
    assert "GigabitEthernet1/0/2" not in out


def test_section_keeps_the_enclosing_header():
    """A hit inside a block is meaningless without knowing which block."""
    out, _ = filter_section(CONFIG, "description uplink")
    assert "interface GigabitEthernet1/0/1" in out


def test_section_is_case_insensitive():
    _, matched = filter_section(CONFIG, "VLAN 200")
    assert matched


def test_no_match_is_reported_rather_than_silently_empty():
    result = prepare(CONFIG, section="ospf", max_chars=10_000)
    assert result.matched is False
    assert result.text == ""
    assert result.total_lines > 0


def test_truncation_cuts_on_a_line_boundary():
    result = prepare(CONFIG, section=None, max_chars=60)
    assert result.truncated
    assert "[truncated" in result.text
    # nothing before the marker may be a partial command
    body = result.text.split("\n\n[truncated")[0]
    assert all(line in CONFIG for line in body.splitlines())


def test_untruncated_text_passes_through():
    result = prepare(CONFIG, section=None, max_chars=10_000)
    assert not result.truncated
    assert result.text == CONFIG
    assert result.returned_lines == result.total_lines
