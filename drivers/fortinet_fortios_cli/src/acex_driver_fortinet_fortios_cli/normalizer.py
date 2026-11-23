import re

from acex_devkit.normalizer import MASK, BaseNormalizer, LineRule, OpResult, RewriteRule

SECRET_SETTINGS = "password|passwd|psksecret|psksecret-remote|secret|auth-pwd|priv-pwd|key|md5-key"


class FortiOSNormalizer(BaseNormalizer):
    line_rules = [
        # The `#config-version=...` and `#conf_file_ver=...` header FortiOS writes ahead of the configuration.
        LineRule("header_comment", re.compile(r"^\s*#")),
    ]

    # A stored secret reads `set password ENC <blob>` and one in clear `set password <text>`. The value goes and the
    # ENC marker, which only says how the value is stored, stays.
    rewrite_rules = [
        RewriteRule(
            "secret_setting",
            re.compile(rf"^(\s*set\s+(?:{SECRET_SETTINGS})(?:\s+ENC)?)\s+\S+.*$"),
            rf"\1 {MASK}",
        ),
    ]

    # A private key is one quoted value that runs over many lines, so a line by line rule cannot reach it.
    private_key = re.compile(r'^(\s*set\s+private-key\s+)"[^"]*"', re.MULTILINE)

    def mask(self, raw: str) -> OpResult:
        return super().mask(self.private_key.sub(rf'\1"{MASK}"', raw))
