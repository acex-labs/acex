"""Unit tests for the SNMP trap / syslog service-input renderers."""

from acex.observability.renderers.telegraf import (
    render_snmp_trap_input,
    render_syslog_input,
)


class TestRenderSnmpTrapInput:
    def test_default_v2c(self):
        out = render_snmp_trap_input()
        assert "[[inputs.snmp_trap]]" in out
        assert 'service_address = "udp://:162"' in out
        assert 'version = "2c"' in out
        # No v3 fields, no community unless provided
        assert "sec_name" not in out
        assert "community" not in out
        # Exactly one block
        assert out.count("[[inputs.snmp_trap]]") == 1

    def test_v2c_with_community(self):
        out = render_snmp_trap_input(version="2c", community="private")
        assert 'community = "private"' in out
        assert out.count("[[inputs.snmp_trap]]") == 1

    def test_v3_includes_auth_fields(self):
        out = render_snmp_trap_input(
            version="3",
            sec_name="monitor",
            auth_protocol="SHA",
            auth_password="authpw",
            sec_level="authPriv",
            priv_protocol="AES",
            priv_password="privpw",
        )
        assert 'version = "3"' in out
        assert 'sec_name = "monitor"' in out
        assert 'auth_protocol = "SHA"' in out
        assert 'auth_password = "authpw"' in out
        assert 'sec_level = "authPriv"' in out
        assert 'priv_protocol = "AES"' in out
        assert 'priv_password = "privpw"' in out
        # v3 blocks must not carry a community
        assert "community" not in out
        assert out.count("[[inputs.snmp_trap]]") == 1

    def test_v3_omits_unset_fields(self):
        out = render_snmp_trap_input(version="3")
        assert 'version = "3"' in out
        for field in ("sec_name", "auth_protocol", "auth_password", "sec_level", "priv_protocol", "priv_password"):
            assert field not in out

    def test_both_renders_single_v3_block(self):
        """ "both" cannot bind two listeners to the same UDP port, so it
        collapses to one v3 block (gosnmp still accepts v2c traps)."""
        out = render_snmp_trap_input(
            version="both",
            sec_name="monitor",
            sec_level="authNoPriv",
            auth_protocol="SHA",
            auth_password="authpw",
        )
        assert out.count("[[inputs.snmp_trap]]") == 1
        assert 'version = "3"' in out
        assert 'sec_name = "monitor"' in out
        assert 'auth_protocol = "SHA"' in out

    def test_custom_port(self):
        out = render_snmp_trap_input(service_address="udp://:1162")
        assert 'service_address = "udp://:1162"' in out


class TestRenderSyslogInput:
    def test_default(self):
        out = render_syslog_input()
        assert "[[inputs.syslog]]" in out
        assert 'server = "udp://:514"' in out
        assert 'syslog_standard = "RFC5424"' in out

    def test_custom_server(self):
        out = render_syslog_input(server="udp://:1514")
        assert 'server = "udp://:1514"' in out
