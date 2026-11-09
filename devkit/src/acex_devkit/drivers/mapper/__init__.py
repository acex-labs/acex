"""Declarative render+parse for CLI configuration text.

A driver declares one `Block` per component type (or `Dispatch`ed family) with the lines that
express its fields. Each declaration — `Line`, `Flag`, `Multiline`, `Mount`, `Section`, nested
`Block` — both renders and parses, so the two directions can't drift apart. `Mapper` runs both
directions over the top-level blocks.
"""

from acex_devkit.drivers.mapper.context import Context
from acex_devkit.drivers.mapper.mapper import Mapper
from acex_devkit.drivers.mapper.syntax import (
    Augment,
    Block,
    Dispatch,
    Flag,
    Item,
    Line,
    Mount,
    Multiline,
    Pattern,
    Section,
)
from acex_devkit.drivers.mapper.tokens import (
    TOKENS,
    Choice,
    Int,
    Ipv4Mask,
    Keyword,
    Pointer,
    Range,
    Rest,
    Token,
    Vlans,
    Words,
)

__all__ = [
    "Augment",
    "Block",
    "Choice",
    "Context",
    "Dispatch",
    "Flag",
    "Int",
    "Ipv4Mask",
    "Item",
    "Keyword",
    "Line",
    "Mapper",
    "Mount",
    "Multiline",
    "Pattern",
    "Pointer",
    "Range",
    "Rest",
    "Section",
    "TOKENS",
    "Token",
    "Vlans",
    "Words",
]
