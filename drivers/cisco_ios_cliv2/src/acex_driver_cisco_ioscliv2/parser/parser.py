"""Cisco IOS CLI parser.

Parses raw running-config text into a `ComposedConfiguration` via the DialectAttributeMap/
Mapper concept (see /Users/johan/.claude/plans/validated-finding-petal.md) — the same
`INTERFACE_MAPS` that `CiscoIOSCLIRenderer` renders from, so render and parse can't drift apart.

Interfaces are the only section covered so far. Other sections (system, ntp, ssh, dns, clock,
SVI/L3 interfaces) previously went through per-section `ntc_templates`/TextFSM calls; that
approach is being retired in favor of DialectAttributeMaps, not repaired, so it's been removed
rather than carried forward — they'll come back as their own attribute maps.
"""

from typing import Any

from acex_devkit.drivers import ParserBase
from acex_devkit.drivers.mapper import Mapper
from acex_devkit.models.composed_configuration import ComposedConfiguration
from pydantic import BaseModel

from acex_driver_cisco_ioscliv2.dialect import INTERFACE_MAPS, SYSTEM_MAPS, CiscoDialect


class CiscoIOSCLIParser(ParserBase):
    def __init__(self):
        self.running_config: str | None = None
        self._parsed_config = ComposedConfiguration()
        self.mapper = Mapper(CiscoDialect(), [*INTERFACE_MAPS, *SYSTEM_MAPS])

    @property
    def parsed_config(self) -> BaseModel:
        return self._parsed_config

    def parse(self, configuration: str) -> dict[str, Any]:
        """Parse the Cisco IOS CLI configuration content."""
        self.running_config = configuration
        self.mapper.parse(configuration, root_factory=lambda: self._parsed_config)
        return self._remove_none_values(self._parsed_config)

    # Only used for local testing with a static config file
    def load_running_config(self, filepath: str) -> str:
        with open(filepath) as f:
            return f.read()

    def _remove_none_values(self, model: BaseModel) -> dict[str, Any]:
        """Drop None-valued keys (and `metadata`) recursively so the output only contains keys
        with actual values — makes downstream diffing easier, since composed configs likewise
        never carry None values."""

        def _remove_none(obj):
            if isinstance(obj, dict):
                return {k: _remove_none(v) for k, v in obj.items() if v is not None and k != "metadata"}
            if isinstance(obj, list):
                return [_remove_none(item) for item in obj if item is not None]
            return obj

        return _remove_none(model.model_dump())
