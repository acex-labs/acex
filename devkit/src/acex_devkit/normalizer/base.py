"""Base normalizer for vendor-specific subclasses.

Subclasses only need to declare rules:

    class MyVendorNormalizer(BaseNormalizer):
        line_rules    = [...]
        block_rules   = [...]
        rewrite_rules = [...]

Optional overrides if the vendor syntax differs:
    is_block_continuation(line) -> bool
    is_block_terminator(line)   -> bool
    post_process(lines, stats)  -> list[str]
"""

from __future__ import annotations

import re

from acex_devkit.normalizer.engine import (
    LineRule,
    BlockRule,
    RewriteRule,
    OpStats,
    OpResult,
    NormalizerEngine,
)


class BaseNormalizer:
    line_rules: list[LineRule] = []
    block_rules: list[BlockRule] = []
    rewrite_rules: list[RewriteRule] = []

    engine: NormalizerEngine = NormalizerEngine()

    # ── hooks (override per vendor) ───────────────────────────────

    def is_block_continuation(self, line: str) -> bool:
        if not line:
            return False
        if line.startswith((" ", "\t")):
            return True
        if re.fullmatch(r"[0-9A-Fa-f ]+", line.rstrip()):
            return True
        return False

    def is_block_terminator(self, line: str) -> bool:
        return line.strip() in ("quit", "exit")

    def post_process(self, lines: list[str], stats: OpStats) -> list[str]:
        return self.engine.collapse_and_trim(lines, stats)

    # ── operations ────────────────────────────────────────────────

    def normalize(self, raw: str) -> OpResult:
        lines, stats = self.engine.normalize_pass(
            raw,
            line_rules=self.line_rules,
            block_rules=self.block_rules,
            is_block_continuation=self.is_block_continuation,
            is_block_terminator=self.is_block_terminator,
        )
        lines = self.post_process(lines, stats)
        stats.lines_out = len(lines)
        return OpResult(
            config="\n".join(lines) + ("\n" if lines else ""),
            operation="normalize",
            stats=stats,
        )

    def mask(self, raw: str) -> OpResult:
        lines, stats = self.engine.mask_pass(
            raw, rewrite_rules=self.rewrite_rules
        )
        return OpResult(
            config="\n".join(lines) + ("\n" if lines else ""),
            operation="mask",
            stats=stats,
        )
