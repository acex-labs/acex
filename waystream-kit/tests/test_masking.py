from ibos_kit.masking import MASK, find_unmasked, mask
from ibos_kit.paths import DEVICE_FIXTURES, GOLDEN, VARIANTS


def test_the_three_secret_syntaxes_from_the_third_party_driver_are_masked():
    text = (
        "snmp-group version 2c\n"
        " community EXAMPLE-RO read-only view all\n"
        " notify 198.51.100.20 community EXAMPLE-TRAP trap\n"
        "radius server 198.51.100.30 secret EXAMPLE-RADIUS\n"
    )
    assert mask(text).text == (
        "snmp-group version 2c\n"
        f" community {MASK} read-only view all\n"
        f" notify 198.51.100.20 community {MASK} trap\n"
        f"radius server 198.51.100.30 secret {MASK}\n"
    )


def test_the_variant_with_secrets_matches_its_golden_file():
    assert mask((VARIANTS / "with-secrets.txt").read_text()).text == (GOLDEN / "with-secrets.masked.txt").read_text()


def test_every_documented_syntax_is_masked_by_its_own_rule_and_the_guesses_are_only_a_safety_net():
    result = mask((VARIANTS / "with-secrets.txt").read_text())
    assert not [name for name in result.hits if name.startswith("guess:")]
    assert set(result.hits) == {
        "snmp_community",
        "snmp_notify_community",
        "radius_server_secret",
        "tacacs_plus_secret",
        "enable_secret",
        "console_password",
        "username_password",
        "snmp_user_password",
        "snmp_notify_user_password",
        "license_key",
    }
    assert result.hits["username_password"] == 2


def test_syntax_nobody_has_shown_is_masked_by_the_guesses_and_reported_as_guesses():
    result = mask((VARIANTS / "invented-secret-syntax.txt").read_text())
    assert result.text == (GOLDEN / "invented-secret-syntax.masked.txt").read_text()
    assert set(result.hits) == {"username_password", "enable_secret", "guess:key"}


def test_a_hash_marker_after_the_secret_stays_and_only_the_secret_goes():
    assert mask("username lab-admin password EXAMPLE-HASH encrypted\n").text == (
        f"username lab-admin password {MASK} encrypted\n"
    )
    assert mask(" notify 198.51.100.21 user nocinfo password EXAMPLE-PW sha\n").text == (
        f" notify 198.51.100.21 user nocinfo password {MASK} sha\n"
    )
    assert mask("tacacs-plus seq 10 server tacacs.example.net secret EXAMPLE-S timeout 2\n").text == (
        f"tacacs-plus seq 10 server tacacs.example.net secret {MASK} timeout 2\n"
    )


def test_a_snmp_user_access_line_is_not_a_secret():
    line = " snmp-user nocinfo readview all\n"
    assert mask(line).text == line


def test_masking_twice_changes_nothing():
    for path in (VARIANTS / "with-secrets.txt", VARIANTS / "invented-secret-syntax.txt"):
        once = mask(path.read_text()).text
        assert mask(once).text == once


def test_a_hit_report_names_rules_and_never_carries_the_secret():
    result = mask("radius server 198.51.100.30 secret EXAMPLE-RADIUS\n")
    assert result.hits == {"radius_server_secret": 1}
    assert "EXAMPLE-RADIUS" not in repr(result.hits)


def test_encryption_type_digit_stays_and_only_the_secret_goes():
    assert mask("enable secret 7 0A1B2C3D\n").text == f"enable secret 7 {MASK}\n"


def test_configuration_without_secrets_is_left_alone():
    for path in sorted(DEVICE_FIXTURES.glob("*/running-config*.txt")):
        text = path.read_text()
        assert mask(text).text == text, path.name


def test_a_keyword_inside_a_longer_word_is_not_a_secret():
    line = "interface gigabitethernet21\n description monkey passwords are not here\n"
    assert mask(line).text == line


def test_line_count_and_order_are_preserved():
    text = (VARIANTS / "with-secrets.txt").read_text()
    assert len(mask(text).text.splitlines()) == len(text.splitlines())


def test_find_unmasked_reports_rule_and_line_number_not_the_value():
    found = find_unmasked("hostname x\nradius server 198.51.100.30 secret EXAMPLE-RADIUS\n")
    assert found == [(2, "radius_server_secret")]
    assert find_unmasked(mask("radius server 198.51.100.30 secret EXAMPLE-RADIUS\n").text) == []
