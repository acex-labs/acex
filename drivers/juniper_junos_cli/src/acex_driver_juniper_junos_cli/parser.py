"""Junos CLI configuration parser.

Parsing a real Junos `show configuration` (hierarchical or set-format) into
the device-agnostic model is a significant undertaking. This stub keeps the
driver instantiable so deployment-side flows (render/render_patch/apply_patch)
work; calling parse() raises until a real implementation lands.
"""

from acex.plugins.neds.core import ParserBase


class JunosCLIParser(ParserBase):
    def parse(self, configuration: str):
        raise NotImplementedError(
            "JunosCLIParser.parse is not yet implemented. "
            "Implement parsing of `show configuration | display set` output here."
        )
