"""Cisco IOS / IOS-XE normalizer — vendor-specific rules only."""

import re

from acex_devkit.normalizer import BaseNormalizer, LineRule, BlockRule, RewriteRule


class CiscoIOSNormalizer(BaseNormalizer):

    line_rules = [
        LineRule("header_building",   re.compile(r"^Building configuration\.\.\.")),
        LineRule("header_current",    re.compile(r"^Current configuration\s*:\s*\d+\s*bytes")),
        LineRule("last_change",       re.compile(r"^!\s*Last configuration change")),
        LineRule("nvram_updated",     re.compile(r"^!\s*NVRAM config last updated")),
        LineRule("no_change",         re.compile(r"^!\s*No configuration change")),
        LineRule("ntp_clock_period",  re.compile(r"^\s*ntp clock-period\s+\d+")),
        LineRule("license_udi",       re.compile(r"^\s*license udi\s+")),
        LineRule("license_boot",      re.compile(r"^\s*license boot level\s+")),
        LineRule("snmp_engineid",     re.compile(r"^\s*snmp-server engineID\s+")),
        LineRule("cts_sxp_dynamic",   re.compile(r"^\s*cts sxp connection peer\s+")),
        LineRule("end_marker",        re.compile(r"^end\s*$")),
        LineRule("version_banner",    re.compile(r"^version\s+\d+\.\d+\s*$")),
        LineRule("boot_marker",       re.compile(r"^\s*boot-start-marker\s*$")),
        LineRule("boot_end_marker",   re.compile(r"^\s*boot-end-marker\s*$")),
    ]

    block_rules = [
        BlockRule("pki_cert_chain",       re.compile(r"^crypto pki certificate chain\s+")),
        BlockRule("pki_trustpoint_self",  re.compile(r"^crypto pki trustpoint\s+TP-self-signed-")),
        BlockRule("pki_certificate_self", re.compile(r"^crypto pki certificate\s+self-signed")),
    ]

    rewrite_rules = [
        RewriteRule(
            "enable_secret",
            re.compile(r"^(\s*enable secret\s+\d+)\s+\S+.*$"),
            r"\1 <REDACTED>",
        ),
        RewriteRule(
            "enable_password",
            re.compile(r"^(\s*enable password(?:\s+\d+)?)\s+\S+.*$"),
            r"\1 <REDACTED>",
        ),
        RewriteRule(
            "username_secret",
            re.compile(r"^(\s*username\s+\S+(?:\s+privilege\s+\d+)?\s+secret\s+\d+)\s+\S+.*$"),
            r"\1 <REDACTED>",
        ),
        RewriteRule(
            "username_password",
            re.compile(r"^(\s*username\s+\S+(?:\s+privilege\s+\d+)?\s+password(?:\s+\d+)?)\s+\S+.*$"),
            r"\1 <REDACTED>",
        ),
        RewriteRule(
            "snmp_community",
            re.compile(r"^(\s*snmp-server community)\s+\S+(\s+.*)?$"),
            r"\1 <REDACTED>\2",
        ),
        RewriteRule(
            "aaa_shared_key",
            re.compile(r"^(\s*key(?:\s+\d+)?)\s+\S+.*$"),
            r"\1 <REDACTED>",
        ),
        RewriteRule(
            "ike_psk",
            re.compile(r"^(\s*pre-shared-key(?:\s+address\s+\S+)?)\s+key\s+\S+.*$"),
            r"\1 key <REDACTED>",
        ),
        RewriteRule(
            "ospf_md5_key",
            re.compile(r"^(\s*ip ospf message-digest-key\s+\d+\s+md5(?:\s+\d+)?)\s+\S+.*$"),
            r"\1 <REDACTED>",
        ),
        RewriteRule(
            "bgp_password",
            re.compile(r"^(\s*neighbor\s+\S+\s+password(?:\s+\d+)?)\s+\S+.*$"),
            r"\1 <REDACTED>",
        ),
    ]
