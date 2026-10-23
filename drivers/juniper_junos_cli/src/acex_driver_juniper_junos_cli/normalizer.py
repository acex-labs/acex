"""Junos normalizer for `show configuration | display set` output — vendor-specific rules only."""

import re

from acex_devkit.normalizer import BaseNormalizer, LineRule, RewriteRule

# A Junos value: a quoted string or a single token.
VALUE = r'("[^"]*"|\S+)'


class JunosNormalizer(BaseNormalizer):
    line_rules = [
        LineRule("last_commit", re.compile(r"^##\s*Last (commit|changed)")),
        LineRule("version", re.compile(r"^set version\s+")),
    ]

    rewrite_rules = [
        RewriteRule(
            "secret_value",
            re.compile(
                rf"^(set .*\b(?:encrypted-password|secret|authentication-key|md5 \d+ key|"
                rf"pre-shared-key (?:ascii-text|hexadecimal)))\s+{VALUE}(.*)$"
            ),
            r'\1 "<REDACTED>"\3',
        ),
        RewriteRule(
            "snmp_community",
            re.compile(rf"^(set snmp community)\s+{VALUE}(.*)$"),
            r'\1 "<REDACTED>"\3',
        ),
    ]
